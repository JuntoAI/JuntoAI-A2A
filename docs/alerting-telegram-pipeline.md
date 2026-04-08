# Alerting Pipeline: CloudWatch → SNS → Telegram

## Overview

JuntoAI runs a centralized alerting pipeline that monitors CloudWatch logs and metrics across all production services, detects errors via metric filters and ML anomaly detection, and delivers formatted notifications to a Telegram group chat in real time.

The pipeline covers three event sources:
1. **Log-based errors** — Pino structured log entries (`level="error"` / `level="fatal"`) from ECS services
2. **Application-level metric alarms** — CPU, memory, error rates, WebSocket disconnections, Bedrock throttling
3. **CI/CD pipeline failures** — CodePipeline execution and action-level failures via EventBridge

All three converge on a single SNS topic → Lambda → Telegram Bot API path.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EVENT SOURCES                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  CloudWatch Logs (Pino JSON)          CloudWatch Metrics            │
│  ┌──────────────────────┐             ┌──────────────────────┐      │
│  │ CareerGraph Service  │             │ ECS CPU/Memory       │      │
│  │ CopyWriter Service   │             │ Bedrock Throttling   │      │
│  └──────┬───────────────┘             │ Error Rates          │      │
│         │                             │ Unhealthy Tasks      │      │
│         ▼                             │ WebSocket Disconnect │      │
│  Metric Filters                       │ DLQ Messages         │      │
│  ┌──────────────────┐                 │ Schedule Errors      │      │
│  │ error level      │                 └──────────┬───────────┘      │
│  │ fatal level      │                            │                  │
│  │ websocket errors │                            │                  │
│  │ bedrock errors   │                            │                  │
│  │ generation errors│                            │                  │
│  └──────┬───────────┘                            │                  │
│         │                                        │                  │
│         ▼                                        ▼                  │
│  CloudWatch Alarms ◄─────────────────────────────┘                  │
│  (threshold breaches)                                               │
│         │                                                           │
│         │    ML Anomaly Detector          EventBridge               │
│         │    ┌──────────────────┐         ┌──────────────────┐      │
│         │    │ CareerGraph logs │         │ CodePipeline      │      │
│         │    │ CopyWriter logs  │         │ FAILED events     │      │
│         │    └──────┬───────────┘         └──────┬───────────┘      │
│         │           │                            │                  │
│         ▼           ▼                            ▼                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              SNS Topic: careergraph-alarms                   │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                   │
│                                 ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │         Lambda: careergraph-telegram-notifier                │   │
│  │         (Node.js 22, 128MB, 10s timeout)                     │   │
│  │                                                              │   │
│  │  1. Parse SNS message                                        │   │
│  │  2. Detect type (Alarm vs CodePipeline)                      │   │
│  │  3. Format HTML message                                      │   │
│  │  4. POST to Telegram Bot API                                 │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                   │
│                                 ▼                                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Telegram Group Chat                        │   │
│  │                                                              │   │
│  │  🚨 ALARM: careergraph-error-level (prod)                    │   │
│  │  🔴 Pipeline FAILED: juntoai-careergraph-frontend-prod       │   │
│  │  ✅ OK: careergraph-fatal-level (prod)                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Infrastructure Files

| File | Purpose |
|------|---------|
| `infra/modules/core/careergraph-monitoring.tf` | SNS topic definition, application-level alarms (CPU, memory, error rates, Bedrock throttling, WebSocket disconnections, unhealthy tasks) |
| `infra/modules/core/careergraph-error-alerting.tf` | Log-based metric filters, log-level alarms, ML anomaly detector, Telegram Lambda function + IAM |
| `infra/modules/core/copywriter-error-alerting.tf` | CopyWriter service metric filters, alarms, and anomaly detector (mirrors CareerGraph pattern) |
| `infra/modules/core/codepipeline-alerting.tf` | EventBridge rules for CodePipeline failures, SNS topic policy |
| `infra/modules/core/cloudwatch-scheduler-alarms.tf` | DLQ alarms, scheduled post failures, schedule creation errors |
| `infra/modules/core/lambda/careergraph-telegram-notifier.mjs` | Lambda source (deployed via Terraform `archive_file`) |
| `infra/lambda-functions/telegram-notifier/index.mjs` | Lambda source (canonical copy, used by unit tests) |

## SNS Topic (Central Hub)

All alarms and events converge on a single SNS topic:

```
Resource: aws_sns_topic.careergraph_alarms
Name:     juntoai-careergraph-alarms-{env}
```

The topic policy allows publishing from:
- CloudWatch Alarms (`cloudwatch.amazonaws.com`)
- EventBridge rules (`events.amazonaws.com`)
- Same-account principals (for future extensibility)

The topic has one subscriber: the Telegram notifier Lambda.

## Detection Layers

### Layer 1: Log-Based Metric Filters

Pino structured JSON logs are parsed by CloudWatch metric filters. Each filter increments a custom metric when a matching log entry is detected.

**CareerGraph Service** (namespace: `CareerGraph`):

| Metric Filter | Pattern | Custom Metric |
|---------------|---------|---------------|
| Error level | `{ $.level = "error" }` | `ErrorLevelCount` |
| Fatal level | `{ $.level = "fatal" }` | `FatalLevelCount` |
| WebSocket errors | `{ $.level = "error" && ($.msg = "*websocket*" \|\| $.msg = "*disconnect*" \|\| $.msg = "*connection*") }` | `WebSocketErrorCount` |
| Bedrock errors | `{ $.level = "error" && ($.msg = "*bedrock*" \|\| $.msg = "*sonic*" \|\| $.msg = "*nova*") }` | `BedrockErrorCount` |

**CopyWriter Service** (namespace: `CopyWriter`):

Same four filters as CareerGraph, plus:

| Metric Filter | Pattern | Custom Metric |
|---------------|---------|---------------|
| Generation errors | `{ $.level = "error" && ($.msg = "*generation*" \|\| $.msg = "*pipeline*" \|\| $.msg = "*style*" \|\| $.msg = "*post-generator*") }` | `GenerationErrorCount` |

### Layer 2: CloudWatch Alarms

Each metric filter feeds a CloudWatch alarm with specific thresholds:

**Log-Based Alarms (CareerGraph + CopyWriter):**

| Alarm | Threshold | Period | Eval Periods | Severity |
|-------|-----------|--------|--------------|----------|
| Error level | >5 errors | 5 min | 2 | Medium |
| Fatal level | >0 fatals | 1 min | 1 | Critical |
| WebSocket errors | >3 errors | 5 min | 2 | Medium |
| Bedrock errors | >3 errors | 5 min | 1 | High |
| Generation errors (CopyWriter only) | >3 errors | 5 min | 2 | Medium |

**Application-Level Alarms (CareerGraph):**

| Alarm | Metric | Threshold |
|-------|--------|-----------|
| High CPU | `AWS/ECS CPUUtilization` | >80% avg over 2×5min |
| High Memory | `AWS/ECS MemoryUtilization` | >85% avg over 2×5min |
| High Error Rate | `CareerGraph/ErrorCount` | >10 in 5min |
| Unhealthy Tasks | `AWS/ApplicationELB HealthyHostCount` | <1 over 2×1min |
| WebSocket Disconnect Rate | `CareerGraph/ConnectionEvents` error/connected ratio | >20% (min 5 connections) |
| Bedrock Throttling (Sonic) | `AWS/Bedrock InvocationThrottles` | >10 in 5min |
| Bedrock Throttling (Lite) | `AWS/Bedrock InvocationThrottles` | >10 in 5min |

**Scheduler Alarms (Echo/CopyWriter):**

| Alarm | Metric | Threshold |
|-------|--------|-----------|
| Post Publisher DLQ | `AWS/SQS ApproximateNumberOfMessagesVisible` | >0 |
| Interview Reminder DLQ | `AWS/SQS ApproximateNumberOfMessagesVisible` | >0 |
| Posts Failed | `JuntoAI/Echo/Scheduler PostsFailed` | >0 |
| Schedule Creation Errors | `JuntoAI/Echo/Scheduler ScheduleCreationErrors` | >0 |

All alarms send both `alarm_actions` (ALARM state) and `ok_actions` (OK recovery) to the SNS topic, so Telegram receives both firing and recovery notifications.

All alarms use `treat_missing_data = "notBreaching"` to avoid false positives during low-traffic periods.

### Layer 3: ML Anomaly Detection

Both CareerGraph and CopyWriter have ML-based log anomaly detectors:

```
Resource: aws_cloudwatch_log_anomaly_detector
Evaluation: Every 5 minutes
Visibility: 21 days
Training: ~2 weeks to learn baseline patterns
```

The anomaly detector learns normal log patterns and flags deviations (new error types, frequency spikes, novel failure modes). Only `HIGH` priority anomalies trigger an alarm → Telegram notification.

### Layer 4: CodePipeline Failures

Two EventBridge rules catch CI/CD failures:

1. **Pipeline Execution Failures** — catches `CodePipeline Pipeline Execution State Change` with `state: FAILED`
2. **Action Execution Failures** — catches `CodePipeline Action Execution State Change` with `state: FAILED` (provides stage-level detail)

Both rules target the same SNS topic. The Lambda detects these events by checking for `source: "aws.codepipeline"` in the parsed message and formats them differently from alarm notifications.

## Lambda Function

**Runtime**: Node.js 22.x, 128MB, 10s timeout

**Source**: `infra/modules/core/lambda/careergraph-telegram-notifier.mjs`

### Event Detection Logic

The Lambda receives SNS events and auto-detects the event type:

```
SNS Message received
  │
  ├─ JSON parse succeeds?
  │   ├─ source === "aws.codepipeline"?
  │   │   └─ YES → Format as pipeline failure (🔴)
  │   └─ NO → Format as CloudWatch alarm (🚨 / ✅)
  │
  └─ JSON parse fails → Format as alarm (best-effort)
```

### Message Formats

**CloudWatch Alarm (ALARM state):**
```
🚨 ALARM: juntoai-careergraph-error-level (prod)

State: ALARM
Time: 2026-04-08T10:30:00.000Z
Description: CareerGraph error-level log count exceeded 5 in 5 minutes...
```

**CloudWatch Alarm (OK recovery):**
```
✅ OK: juntoai-careergraph-error-level (prod)

State: OK
Time: 2026-04-08T10:35:00.000Z
Description: CareerGraph error-level log count exceeded 5 in 5 minutes...
```

**CodePipeline Failure:**
```
🔴 Pipeline FAILED: juntoai-careergraph-frontend-prod (prod)

Stage: Build
Action: CodeBuild
Time: 2026-04-08T10:30:00.000Z
Execution: a1b2c3d4
Region: us-east-2
```

### Secrets Management

The Lambda reads Telegram credentials from AWS SSM Parameter Store:

| SSM Path | Purpose | Encryption |
|----------|---------|------------|
| `/juntoai/{env}/telegram-bot-token` | Telegram Bot API token | `WithDecryption: true` |
| `/juntoai/{env}/telegram-chat-id` | Target chat/group ID | Plaintext |

Credentials are cached at the module level for Lambda warm invocations (no SSM call on subsequent invocations within the same container).

### IAM Permissions

The Lambda role has:
- `AWSLambdaBasicExecutionRole` (CloudWatch Logs)
- Inline policy: `ssm:GetParameter` scoped to the two Telegram SSM paths only

## Integration Test Alerting

In addition to the infrastructure pipeline, integration tests can send Telegram alerts directly:

**File**: `backend/careergraph-service/tests/integration/helpers/alerting.js`

This helper uses the same Telegram Bot API and chat ID (via `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` env vars) to send alerts from test `afterAll` hooks when critical failures are detected.

**Severity levels:**
- 🔴 `CRITICAL` — Dev environment down (Tier 1)
- 🟡 `WARNING` — Write/cleanup issues (Tier 2)
- 🔵 `INFO` — Nova integration issues (Tier 3)

This is a separate code path from the Lambda (uses `fetch()` directly) and only activates when the env vars are set.

## Testing

Unit tests for the Lambda are at:
```
tests/unit/backend/services/telegram-notifier.test.js
```

Tests cover:
- `parseAlarmMessage()` — JSON and non-JSON SNS messages
- `formatTelegramMessage()` — ALARM and OK state formatting
- `isCodePipelineEvent()` — Event type detection
- `parsePipelineEvent()` — Pipeline and action-level event parsing
- `formatPipelineMessage()` — Pipeline failure formatting
- CloudWatch metric filter pattern simulation (error, fatal, websocket, bedrock)
- Property-based tests (fast-check) for alarm description parsing

## Adding a New Service

To add Telegram alerting for a new service:

1. Create metric filters on the service's CloudWatch log group (copy the pattern from `copywriter-error-alerting.tf`)
2. Create CloudWatch alarms referencing the new custom metrics
3. Point `alarm_actions` and `ok_actions` to `aws_sns_topic.careergraph_alarms.arn`
4. Optionally add an ML anomaly detector on the log group
5. No Lambda changes needed — the existing Lambda handles all alarm formats

## Investigating Alerts

Each alarm description includes a CloudWatch Insights query. When you receive a Telegram alert:

1. Open CloudWatch Logs Insights in the AWS Console
2. Select the relevant log group
3. Run the query from the alarm description, e.g.:
   ```
   fields @timestamp, level, msg, sessionId, userId
   | filter level = "error"
   | sort @timestamp desc
   | limit 50
   ```
4. For anomaly alerts, check CloudWatch Logs > Log Anomalies for the service log group
