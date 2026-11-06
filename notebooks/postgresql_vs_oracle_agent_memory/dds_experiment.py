"""Native Deep Data Security demonstration with isolated local end users.

The caller supplies a DBA execution function. The optional Docker adapter uses
OS authentication only on an explicitly named local development container.
No VPD policy or application-set tenant context is used in these checks.
"""
import hashlib
import os
import re
import secrets
import subprocess
from pathlib import Path
import oracledb
oracledb.defaults.program = 'devrel-developerhub-postgresql-versus-oracle-ai-database-for-agent-memory'


def local_admin(container, pdb):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', container):
        raise ValueError('Invalid local container name')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_$#]*', pdb):
        raise ValueError('Invalid PDB name')
    def execute(sql):
        script=('set echo off feedback off verify off\n'
                'whenever sqlerror exit failure\n'
                f'ALTER SESSION SET CONTAINER={pdb};\n{sql};\nEXIT\n')
        result=subprocess.run(['docker','exec','-i',container,'sqlplus','-s','/','as','sysdba'],
            input=script,text=True,capture_output=True,timeout=60)
        if result.returncode:
            # SQL*Plus may echo the failing DDL containing a generated password.
            codes=re.findall(r'(?:ORA|SP2)-\d+', result.stdout+result.stderr)
            raise RuntimeError('DDS administrative statement failed: '+(', '.join(codes) or 'SQL*Plus error'))
    return execute


def run_dds(lab, admin):
    owner=lab.oq('SELECT USER FROM dual')[0][0]
    if not re.fullmatch(r'[A-Z][A-Z0-9_$#]*',owner):
        raise ValueError('This example requires a simple unquoted schema name')
    prefix=lab.prefix+'_DDS'
    table=prefix+'_M'
    qualified=owner+'.'+table
    support,finance=prefix+'_SUP',prefix+'_FIN'
    support_role,finance_role,login=prefix+'_SR',prefix+'_FR',prefix+'_LOGIN'
    # Reset this notebook's exact DDS names after an interrupted run.
    reset = [f'DROP DATA GRANT IF EXISTS {owner}.{prefix}_G{i}' for i in (1, 2, 3)]
    reset += [f'DROP END USER IF EXISTS {user}' for user in (support, finance)]
    reset += [f'DROP DATA ROLE IF EXISTS {role}' for role in (support_role, finance_role)]
    reset += [f'DROP ROLE IF EXISTS {login}', f'DROP TABLE IF EXISTS {qualified} PURGE']
    admin(';\n'.join(reset))
    password='PGOx'+secrets.token_hex(24)
    undo=[]
    def create(sql,drop):
        admin(sql);undo.insert(0,drop)
    result=dict(oracle=lab.o.version,authentication='Locally managed DDS end users, direct password logon',
        scope='Native data grants: row filtering and per-row sensitive-column masking. No IAM/JWT or pooled application identity test.',
        table=qualified,ddl=[],observations={})
    try:
        lab.oq(f'CREATE TABLE {table}(id NUMBER PRIMARY KEY,tenant_id VARCHAR2(20),content VARCHAR2(200),payment_amount NUMBER)')
        undo.append(f'DROP TABLE {qualified} PURGE')
        for row in [(1,'acme','Support-owned billing case',125),(2,'acme','Finance-owned billing case',950),(3,'globex','Another tenant billing case',700)]:
            lab.oq(f'INSERT INTO {table} VALUES(:i,:t,:c,:p)',i=row[0],t=row[1],c=row[2],p=row[3])
        lab.o.commit()
        create(f'CREATE ROLE {login}',f'DROP ROLE {login}')
        admin(f'GRANT CREATE SESSION TO {login}')
        for user,role in [(support,support_role),(finance,finance_role)]:
            create(f'CREATE DATA ROLE {role}',f'DROP DATA ROLE {role}')
            admin(f'GRANT {login} TO {role}')
            create(f'CREATE END USER {user} IDENTIFIED BY "{password}"',f'DROP END USER {user}')
            admin(f'GRANT DATA ROLE {role} TO {user}')
        grants=[
          (prefix+'_G1',f"SELECT (ALL COLUMNS EXCEPT payment_amount) ON {qualified} WHERE tenant_id='acme' TO {support_role}"),
          (prefix+'_G2',f"SELECT ON {qualified} WHERE tenant_id='acme' AND id=1 TO {support_role}"),
          (prefix+'_G3',f"SELECT ON {qualified} WHERE tenant_id='acme' TO {finance_role}")]
        for name,clause in grants:
            sql=f'CREATE DATA GRANT {owner}.{name} AS {clause}'
            create(sql,f'DROP DATA GRANT {owner}.{name}')
            result['ddl'].append(sql)
        for label,user,expected in [('support',support,[(1,'acme','Support-owned billing case',125),(2,'acme','Finance-owned billing case',None)]),
                                    ('finance',finance,[(1,'acme','Support-owned billing case',125),(2,'acme','Finance-owned billing case',950)])]:
            with oracledb.connect(user=user,password=password,dsn=lab.cfg['dsn']) as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT ORA_END_USER_CONTEXT.username FROM dual')
                    identity=cur.fetchone()[0]
                    lab.check('dds_'+label+'_identity',identity==user)
                    # Deliberately no tenant filter in the reader's SQL.
                    sql=f'SELECT id,tenant_id,content,payment_amount FROM {qualified} ORDER BY id'
                    cur.execute(sql);rows=cur.fetchall()
                    lab.check('dds_'+label+'_row_and_cell_access',rows==expected,rows=rows)
                    cur.execute(f"SELECT COUNT(*) FROM {qualified} WHERE tenant_id='globex' OR 1=1")
                    count=cur.fetchone()[0]
                    lab.check('dds_'+label+'_broad_predicate',count==2,count=count)
                    cur.execute(f'SELECT COUNT(payment_amount) FROM {qualified}')
                    count=cur.fetchone()[0]
                    lab.check('dds_'+label+'_authorized_payment_count',count==(1 if label=='support' else 2),count=count)
                    result['observations'][label]=dict(identity=identity,sql=sql,rows=rows)
        # Even a syntactically valid end-user name cannot replace authentication.
        try:
            conn=oracledb.connect(user=finance,password='PGOx'+secrets.token_hex(24),dsn=lab.cfg['dsn'])
        except oracledb.DatabaseError as exc:
            code=exc.args[0].code
            lab.check('dds_wrong_password_rejected',code==1017,error_code=code)
        else:
            conn.close();lab.check('dds_wrong_password_rejected',False)
        result['status']='passed'
        return result
    finally:
        failed=[]
        for sql in undo:
            try:admin(sql)
            except Exception:failed.append(sql.split()[1]+' cleanup failed')
        lab.check('dds_cleanup',not failed,failures=failed)


def configured_dds(lab):
    lab.report.setdefault('source_sha256',{})['dds_experiment.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    container=os.getenv('PG_ORACLE_DDS_CONTAINER')
    if not container:
        result=dict(status='not_run',reason='Set PG_ORACLE_DDS_CONTAINER and PG_ORACLE_DDS_PDB for the optional local Free demonstration, or call run_dds with your DBA executor.')
    else:
        pdb=os.getenv('PG_ORACLE_DDS_PDB')
        if not pdb:raise ValueError('Set PG_ORACLE_DDS_PDB explicitly to the development PDB')
        result=run_dds(lab,local_admin(container,pdb))
    lab.report['deep_data_security']=result
    return result
