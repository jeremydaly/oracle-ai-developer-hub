"""A 100-memory synthetic corpus with eight fully judged questions."""
import json
from pathlib import Path

CORPUS_VERSION = 'synthetic-100'
DOCS = [{'id': 'm01',
  'tenant': 'acme',
  'active': 1,
  'content': 'For Project Cedar, Priya is the release approver. Production rollout requires her written '
             'approval.'},
 {'id': 'm02',
  'tenant': 'acme',
  'active': 1,
  'content': 'Project Cedar deployment checklist: run migrations, verify health checks, then request release '
             'approval.'},
 {'id': 'm03',
  'tenant': 'acme',
  'active': 1,
  'content': 'For Project Maple, Jonah is the release approver. Maple has a separate release calendar.'},
 {'id': 'm04',
  'tenant': 'acme',
  'active': 0,
  'content': 'Cedar previously used Marco as release approver. This historical policy was superseded by '
             'Priya.'},
 {'id': 'm05',
  'tenant': 'acme',
  'active': 1,
  'content': 'Incident AX417: a stale DNS cache caused checkout failures. Flush the resolver cache and retry '
             'the checkout.'},
 {'id': 'm06',
  'tenant': 'acme',
  'active': 1,
  'content': 'Incident AX471: payment authorization timed out because the upstream payment provider was '
             'unavailable.'},
 {'id': 'm07',
  'tenant': 'acme',
  'active': 1,
  'content': 'Checkout recovery guide: resolver cache invalidation fixes stale DNS answers after an endpoint '
             'change.'},
 {'id': 'm08',
  'tenant': 'acme',
  'active': 1,
  'content': 'The billing service retains invoices for seven years. Invoice retention differs from '
             'conversation retention.'},
 {'id': 'm09',
  'tenant': 'acme',
  'active': 1,
  'content': 'Customer chat transcripts must be erased after thirty days, including derived summaries and '
             'cached prompts.'},
 {'id': 'm10',
  'tenant': 'acme',
  'active': 1,
  'content': 'Deleting a source conversation requires deleting summaries and cached answers derived from '
             'that conversation.'},
 {'id': 'm11',
  'tenant': 'acme',
  'active': 1,
  'content': 'Telemetry logs are kept for ninety days for diagnosing application failures.'},
 {'id': 'm12',
  'tenant': 'acme',
  'active': 1,
  'content': 'Mina prefers concise email updates and does not want meeting invitations for routine status '
             'changes.'},
 {'id': 'm13',
  'tenant': 'acme',
  'active': 1,
  'content': 'Mina needs SMS alerts for urgent production outages. Routine progress reports should go by '
             'email.'},
 {'id': 'm14',
  'tenant': 'acme',
  'active': 1,
  'content': 'Luis prefers weekly video meetings and detailed slide decks for project status.'},
 {'id': 'm15',
  'tenant': 'acme',
  'active': 1,
  'content': 'Refunds above 500 dollars require approval from a finance manager before the refund tool can '
             'execute.'},
 {'id': 'm16',
  'tenant': 'acme',
  'active': 1,
  'content': 'Refunds up to 500 dollars may be issued by the support agent after the purchase is verified.'},
 {'id': 'm17',
  'tenant': 'acme',
  'active': 1,
  'content': 'The refund tool accepts a purchase identifier and an amount in cents. It must receive an '
             'idempotency key.'},
 {'id': 'm18',
  'tenant': 'acme',
  'active': 1,
  'content': 'For HTTP 429 responses, respect Retry-After and use exponential backoff with jitter.'},
 {'id': 'm19',
  'tenant': 'acme',
  'active': 1,
  'content': 'Do not retry a payment submission without an idempotency key. Duplicate payments can result.'},
 {'id': 'm20',
  'tenant': 'acme',
  'active': 1,
  'content': 'HTTP 401 means credentials are missing or invalid. Refresh authentication before attempting '
             'the request again.'},
 {'id': 'm21',
  'tenant': 'acme',
  'active': 1,
  'content': 'The sandbox uses the EU West test endpoint. Production requests must use the EU Central '
             'endpoint.'},
 {'id': 'm22',
  'tenant': 'acme',
  'active': 1,
  'content': 'EU Central production endpoint credentials are stored in the application secret manager.'},
 {'id': 'm23',
  'tenant': 'acme',
  'active': 1,
  'content': 'The staging endpoint accepts synthetic customer data only. Never copy production customer '
             'records into staging.'},
 {'id': 'm24',
  'tenant': 'acme',
  'active': 1,
  'content': 'The Atlas ingestion worker was paused because an expired certificate prevented TLS '
             'connections. Renew the certificate and restart ingestion.'},
 {'id': 'm25',
  'tenant': 'acme',
  'active': 1,
  'content': 'Atlas query workers are healthy. The ingestion backlog will drain after certificate renewal.'},
 {'id': 'm26',
  'tenant': 'acme',
  'active': 1,
  'content': 'The Beacon ingestion worker stopped because its disk was full. Remove temporary files before '
             'restarting.'},
 {'id': 'm27',
  'tenant': 'acme',
  'active': 1,
  'content': 'Cedar approval history: Marco approved the initial prototype. Priya now owns production '
             'approval.'},
 {'id': 'm28',
  'tenant': 'acme',
  'active': 1,
  'content': 'A customer can request erasure before the normal thirty day chat retention period expires.'},
 {'id': 'xm01',
  'tenant': 'other',
  'active': 1,
  'content': 'For Project Cedar, Priya is the release approver. Production rollout requires her written '
             'approval.'},
 {'id': 'xm02',
  'tenant': 'other',
  'active': 1,
  'content': 'Project Cedar deployment checklist: run migrations, verify health checks, then request release '
             'approval.'},
 {'id': 'xm03',
  'tenant': 'other',
  'active': 1,
  'content': 'For Project Maple, Jonah is the release approver. Maple has a separate release calendar.'},
 {'id': 'xm04',
  'tenant': 'other',
  'active': 1,
  'content': 'Cedar previously used Marco as release approver. This historical policy was superseded by '
             'Priya.'},
 {'id': 'm29',
  'tenant': 'acme',
  'active': 1,
  'content': "Cedar production release authorization: attach Priya's written sign-off to the rollout ticket "
             'before deploying.'},
 {'id': 'm30',
  'tenant': 'acme',
  'active': 1,
  'content': 'If Cedar release approval is missing, contact Priya and hold the rollout. Passing automated '
             'checks does not replace her authorization.'},
 {'id': 'm31',
  'tenant': 'acme',
  'active': 1,
  'content': 'The Cedar backup job writes encrypted snapshots at 02:00 UTC. The platform team checks '
             'snapshot completion each morning.'},
 {'id': 'm32',
  'tenant': 'acme',
  'active': 1,
  'content': 'Maple release approval belongs to Jonah. A Cedar project membership does not grant permission '
             'to approve Maple deployments.'},
 {'id': 'm33',
  'tenant': 'acme',
  'active': 1,
  'content': 'Cedar deployment artifacts are signed by the build service and retained for ninety days in the '
             'artifact registry.'},
 {'id': 'm34',
  'tenant': 'acme',
  'active': 1,
  'content': 'Cedar release dashboards display green for healthy services and amber for elevated latency. '
             'Dashboard colors are configured by the operations team.'},
 {'id': 'm35',
  'tenant': 'acme',
  'active': 1,
  'content': "AX417 recovery procedure: flush the checkout resolver's DNS cache, confirm the new endpoint "
             'address, then retry the failed checkout.'},
 {'id': 'm36',
  'tenant': 'acme',
  'active': 1,
  'content': 'The AX417 investigation found that checkout workers cached the old DNS answer after an '
             'endpoint change. Resolver cache invalidation restored connectivity.'},
 {'id': 'm37',
  'tenant': 'acme',
  'active': 1,
  'content': 'AX418 checkout failures affect browsers with an expired cart cookie. Clear the cart cookie and '
             'rebuild the basket.'},
 {'id': 'm38',
  'tenant': 'acme',
  'active': 1,
  'content': 'AX471 payment failures require waiting for the upstream authorization provider to recover. '
             'Flushing DNS does not resolve that incident.'},
 {'id': 'm39',
  'tenant': 'acme',
  'active': 1,
  'content': 'The checkout address form validates postal codes against the selected country before '
             'submitting an order.'},
 {'id': 'm40',
  'tenant': 'acme',
  'active': 1,
  'content': 'The incident dashboard can export AX417 and AX471 charts as PNG files. Chart colors follow the '
             'reporting theme.'},
 {'id': 'm41',
  'tenant': 'acme',
  'active': 1,
  'content': 'The conversation retention scheduler erases customer transcripts and derived summaries thirty '
             'days after the conversation closes.'},
 {'id': 'm42',
  'tenant': 'acme',
  'active': 1,
  'content': 'An approved customer erasure request triggers deletion of that conversation and its derived '
             'summaries before the normal thirty-day retention deadline.'},
 {'id': 'm43',
  'tenant': 'acme',
  'active': 1,
  'content': 'Internal product-training videos are retained for one year. They are stored in the learning '
             'portal, separately from customer chats.'},
 {'id': 'm44',
  'tenant': 'acme',
  'active': 1,
  'content': 'Invoice retention is seven years even when a customer closes an account. The billing archive '
             'has its own retention schedule.'},
 {'id': 'm45',
  'tenant': 'acme',
  'active': 1,
  'content': 'Public FAQ pages are revised every quarter and remain published until the documentation owner '
             'replaces them.'},
 {'id': 'm46',
  'tenant': 'acme',
  'active': 1,
  'content': 'Conversation transcript exports use UTF-8 encoding and include a header row. The download '
             'button appears in the transcript viewer.'},
 {'id': 'm47',
  'tenant': 'acme',
  'active': 1,
  'content': "For Mina's routine project updates, send a short email with the current status and next step; "
             'do not book a status meeting.'},
 {'id': 'm48',
  'tenant': 'acme',
  'active': 1,
  'content': 'Mina requested that routine progress reports stay in the existing email thread so she can '
             'review them together.'},
 {'id': 'm49',
  'tenant': 'acme',
  'active': 1,
  'content': 'Nina prefers routine project updates by SMS. Nina and Mina are different contacts in the '
             'customer directory.'},
 {'id': 'm50',
  'tenant': 'acme',
  'active': 1,
  'content': 'Luis wants a detailed slide deck before his weekly project-status video meeting.'},
 {'id': 'm51',
  'tenant': 'acme',
  'active': 1,
  'content': "Mina's calendar uses the Europe/Paris time zone. Her normal working day starts at 09:00 local "
             'time.'},
 {'id': 'm52',
  'tenant': 'acme',
  'active': 1,
  'content': 'Mina owns the annual design-tool subscription budget. Procurement sends renewal invoices to '
             'the finance mailbox.'},
 {'id': 'm53',
  'tenant': 'acme',
  'active': 1,
  'content': "A 750-dollar refund exceeds the support agent's 500-dollar authority. Obtain a finance "
             "manager's approval before executing the refund."},
 {'id': 'm54',
  'tenant': 'acme',
  'active': 1,
  'content': 'When a requested refund exceeds 500 dollars, the support workflow pauses at the '
             'finance-approval step. A verified purchase alone is insufficient.'},
 {'id': 'm55',
  'tenant': 'acme',
  'active': 1,
  'content': 'A purchase totaling 750 dollars earns 750 loyalty points. Loyalty credits are posted after the '
             'order ships.'},
 {'id': 'm56',
  'tenant': 'acme',
  'active': 1,
  'content': 'Supplier invoices above 2000 dollars require a procurement review. This review applies to '
             'vendor payments, not customer refunds.'},
 {'id': 'm57',
  'tenant': 'acme',
  'active': 1,
  'content': 'The refund history screen uses a blue icon for completed transactions and a grey icon for '
             'pending transactions.'},
 {'id': 'm58',
  'tenant': 'acme',
  'active': 1,
  'content': 'Finance reports customer refund totals separately from promotional discounts in the monthly '
             'revenue dashboard.'},
 {'id': 'm59',
  'tenant': 'acme',
  'active': 1,
  'content': 'After an HTTP 429 rate-limit response, wait for the Retry-After interval before sending the '
             'next request. Avoid immediate repeated retries.'},
 {'id': 'm60',
  'tenant': 'acme',
  'active': 1,
  'content': 'If a rate-limit response has no Retry-After header, retry with capped exponential backoff and '
             'random jitter rather than a tight loop.'},
 {'id': 'm61',
  'tenant': 'acme',
  'active': 1,
  'content': 'After HTTP 401, refresh the access token. Authentication failures are counted separately from '
             'rate-limit responses.'},
 {'id': 'm62',
  'tenant': 'acme',
  'active': 1,
  'content': 'The rate-limit dashboard groups historical HTTP 429 counts by client identifier and calendar '
             'day.'},
 {'id': 'm63',
  'tenant': 'acme',
  'active': 1,
  'content': 'The API plan comparison page lists the request quotas included with each subscription tier.'},
 {'id': 'm64',
  'tenant': 'acme',
  'active': 1,
  'content': 'The network bandwidth chart measures bytes per second on the service interface. It does not '
             'show HTTP response codes.'},
 {'id': 'm65',
  'tenant': 'acme',
  'active': 1,
  'content': 'Live production API clients must use the EU Central endpoint. The EU West endpoint is reserved '
             'for sandbox requests.'},
 {'id': 'm66',
  'tenant': 'acme',
  'active': 1,
  'content': 'Production API routing sends live customer traffic to EU Central; test-environment endpoint '
             'settings must not be copied into production.'},
 {'id': 'm67',
  'tenant': 'acme',
  'active': 1,
  'content': 'The EU West load-test runner sends synthetic requests to the sandbox environment during '
             'scheduled capacity tests.'},
 {'id': 'm68',
  'tenant': 'acme',
  'active': 1,
  'content': 'Static documentation images are cached by the APAC content-delivery nodes. This setting does '
             'not route application API requests.'},
 {'id': 'm69',
  'tenant': 'acme',
  'active': 1,
  'content': 'Encrypted backup copies are archived in EU West. The backup location is independent of the '
             'live API endpoint.'},
 {'id': 'm70',
  'tenant': 'acme',
  'active': 1,
  'content': 'The EU East analytics replica serves overnight business reports. It does not accept live '
             'production API traffic.'},
 {'id': 'm71',
  'tenant': 'acme',
  'active': 1,
  'content': 'Atlas ingestion recovery requires renewing the expired TLS certificate and restarting the '
             'ingestion worker so it can reconnect.'},
 {'id': 'm72',
  'tenant': 'acme',
  'active': 1,
  'content': 'After the Atlas certificate is renewed and ingestion restarts, monitor the queued backlog '
             'until processing catches up. The expired certificate caused the pause.'},
 {'id': 'm73',
  'tenant': 'acme',
  'active': 1,
  'content': 'The Atlas capacity report charts daily ingestion volume and storage growth for the previous '
             'twelve months.'},
 {'id': 'm74',
  'tenant': 'acme',
  'active': 1,
  'content': 'Beacon ingestion cannot resume until temporary files are removed from its full disk. Its '
             'service uses a separate storage volume.'},
 {'id': 'm75',
  'tenant': 'acme',
  'active': 1,
  'content': 'Maple renews its public website certificate automatically through the edge gateway. Its '
             'certificate is separate from Atlas worker credentials.'},
 {'id': 'm76',
  'tenant': 'acme',
  'active': 1,
  'content': 'Atlas report downloads are available to members of the analytics-reader group. Group '
             'membership is reviewed quarterly.'},
 {'id': 'm77',
  'tenant': 'acme',
  'active': 1,
  'content': 'The documentation footer supports English, French, and German. The selected language is saved '
             'in the browser preference.'},
 {'id': 'm78',
  'tenant': 'acme',
  'active': 1,
  'content': 'Warehouse deliveries use loading dock three between 08:00 and 16:00. Drivers check in at the '
             'reception desk.'},
 {'id': 'm79',
  'tenant': 'acme',
  'active': 1,
  'content': 'Employees submit hotel receipts through the travel portal. The nightly reimbursement cap is '
             'listed in the travel policy.'},
 {'id': 'm80',
  'tenant': 'acme',
  'active': 1,
  'content': 'The administration console inherits its light or dark theme from the browser unless the user '
             'selects an override.'},
 {'id': 'm81',
  'tenant': 'acme',
  'active': 0,
  'content': 'Superseded Cedar release policy: Marco approves production releases. This record is inactive '
             'and must not authorize a current rollout.'},
 {'id': 'm82',
  'tenant': 'acme',
  'active': 0,
  'content': 'Superseded AX417 workaround: restart the payment gateway. The later investigation replaced '
             'this advice with DNS cache invalidation.'},
 {'id': 'm83',
  'tenant': 'acme',
  'active': 0,
  'content': 'Retired conversation retention policy: customer transcripts and summaries were kept for ninety '
             'days. The current limit is thirty days.'},
 {'id': 'm84',
  'tenant': 'acme',
  'active': 0,
  'content': "Mina's old communication preference requested weekly status meetings. She replaced it with "
             'concise routine email updates.'},
 {'id': 'm85',
  'tenant': 'acme',
  'active': 0,
  'content': 'Retired refund policy allowed support agents to issue refunds up to 1000 dollars without '
             'finance approval. That limit no longer applies.'},
 {'id': 'm86',
  'tenant': 'acme',
  'active': 0,
  'content': 'Obsolete rate-limit advice recommended immediate retries after HTTP 429. Clients must follow '
             'the current backoff policy instead.'},
 {'id': 'm87',
  'tenant': 'acme',
  'active': 0,
  'content': 'Retired production routing sent live API traffic to EU West. Current production traffic '
             'belongs in EU Central.'},
 {'id': 'm88',
  'tenant': 'acme',
  'active': 0,
  'content': 'An early, superseded Atlas diagnosis blamed a full disk. The confirmed cause was an expired '
             'TLS certificate.'},
 {'id': 'xq1',
  'tenant': 'other',
  'active': 1,
  'content': 'For Project Cedar, Omar approves production releases. This release policy belongs to another '
             'tenant.'},
 {'id': 'xq2',
  'tenant': 'other',
  'active': 1,
  'content': 'Incident AX417 in this tenant was caused by a disabled checkout feature flag. Re-enable the '
             'flag to recover.'},
 {'id': 'xq3',
  'tenant': 'other',
  'active': 1,
  'content': 'This tenant erases customer conversations and derived summaries after sixty days.'},
 {'id': 'xq4',
  'tenant': 'other',
  'active': 1,
  'content': 'Mina in this tenant prefers routine project updates through weekly video calls.'},
 {'id': 'xq5',
  'tenant': 'other',
  'active': 1,
  'content': 'This tenant allows its support agents to issue verified refunds up to 1000 dollars without '
             'finance approval.'},
 {'id': 'xq6',
  'tenant': 'other',
  'active': 1,
  'content': "This tenant's private gateway requires a fixed two-minute pause after every rate-limit "
             'response.'},
 {'id': 'xq7',
  'tenant': 'other',
  'active': 1,
  'content': 'This tenant routes live production API traffic to the US East endpoint.'},
 {'id': 'xq8',
  'tenant': 'other',
  'active': 1,
  'content': 'Atlas ingestion in this tenant stopped because a storage quota was exceeded. Increase the '
             'quota and restart the worker.'}]

QUERIES = [{'id': 'q1', 'text': 'Who must approve the Cedar production release?', 'lexical': 'Cedar approval release'},
 {'id': 'q2', 'text': 'How do I fix checkout error AX417?', 'lexical': 'AX417 checkout'},
 {'id': 'q3',
  'text': 'When must customer conversations and their summaries be removed?',
  'lexical': 'conversation transcripts retention summaries'},
 {'id': 'q4', 'text': 'How should I send Mina a routine project update?', 'lexical': 'Mina routine email'},
 {'id': 'q5',
  'text': 'Can a support agent refund 750 dollars without additional approval?',
  'lexical': 'refund approval finance'},
 {'id': 'q6',
  'text': 'What should a client do after a rate limit response?',
  'lexical': '429 Retry After backoff'},
 {'id': 'q7',
  'text': 'Which region should handle live production API traffic?',
  'lexical': 'production endpoint EU'},
 {'id': 'q8',
  'text': 'Why did Atlas stop ingesting and how do I recover it?',
  'lexical': 'Atlas ingestion certificate'}]

QRELS = json.loads(Path(__file__).with_name('qrels.json').read_text())
for question in QUERIES:
    question['qrels'] = {memory_id: judgment['grade']
                         for memory_id, judgment in QRELS['judgments'][question['id']].items()}


def validate_fixture():
    ids = {d['id'] for d in DOCS}
    eligible = {d['id'] for d in DOCS if d['tenant'] == 'acme' and d['active'] == 1}
    assert len(DOCS) == len(ids) == 100, 'Expected exactly 100 unique memories'
    assert len(eligible) == 79
    assert sum(d['tenant'] == 'acme' and d['active'] == 0 for d in DOCS) == 9
    assert sum(d['tenant'] == 'other' for d in DOCS) == 12
    assert len(QUERIES) == len({q['id'] for q in QUERIES}) == 8
    assert set(QRELS['judgments']) == {q['id'] for q in QUERIES}
    assert all(d['content'].strip() and len(d['content']) <= 2000 for d in DOCS)
    for question in QUERIES:
        judgments = QRELS['judgments'][question['id']]
        assert set(judgments) == ids, 'Every question must judge every memory'
        assert any(j['grade'] > 0 for j in judgments.values())
        for memory_id, judgment in judgments.items():
            assert type(judgment['grade']) is int and 0 <= judgment['grade'] <= 3
            assert judgment['reason'].strip(), 'Every judgment needs a rationale'
            assert memory_id in eligible or judgment['grade'] == 0


validate_fixture()
