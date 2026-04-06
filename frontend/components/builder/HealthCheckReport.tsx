"use client";

import { useState, useEffect, useRef } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Info,
  Loader2,
  RefreshCw,
  CheckCircle2,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import type {
  HealthCheckFinding,
  HealthCheckFullReport,
} from "@/lib/builder/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface HealthCheckReportProps {
  findings: HealthCheckFinding[];
  report: HealthCheckFullReport | null;
  isAnalyzing: boolean;
  onRetry?: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIMEOUT_MS = 60_000;

const TIER_CONFIG = {
  Ready: { color: "bg-green-500", textColor: "text-green-400", icon: CheckCircle2 },
  "Needs Work": { color: "bg-yellow-500", textColor: "text-yellow-400", icon: AlertTriangle },
  "Not Ready": { color: "bg-red-500", textColor: "text-red-400", icon: XCircle },
} as const;

const SEVERITY_CONFIG = {
  critical: { color: "text-red-500", bgColor: "bg-red-500/10", icon: AlertCircle },
  warning: { color: "text-yellow-500", bgColor: "bg-yellow-500/10", icon: AlertTriangle },
  info: { color: "text-blue-400", bgColor: "bg-blue-400/10", icon: Info },
} as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function HealthCheckReport({
  findings,
  report,
  isAnalyzing,
  onRetry,
}: HealthCheckReportProps) {
  const [timedOut, setTimedOut] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Start/reset timeout when analyzing begins
  useEffect(() => {
    if (isAnalyzing) {
      setTimedOut(false);
      timerRef.current = setTimeout(() => {
        setTimedOut(true);
      }, TIMEOUT_MS);
    } else {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isAnalyzing]);

  // Timeout state
  if (timedOut && !report) {
    return (
      <div
        className="rounded-lg border border-red-500/30 bg-red-500/10 p-6 text-center"
        data-testid="health-check-timeout"
      >
        <ShieldAlert className="mx-auto mb-3 text-red-500" size={32} />
        <p className="text-sm font-medium text-red-400">
          Health check timed out
        </p>
        <p className="mt-1 text-xs text-gray-400">
          The analysis took longer than expected.
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-red-500/20 px-4 py-2 text-sm text-red-400 hover:bg-red-500/30 transition-colors"
            data-testid="retry-button"
          >
            <RefreshCw size={14} />
            Retry Health Check
          </button>
        )}
      </div>
    );
  }

  // Loading state
  if (isAnalyzing && !report) {
    return (
      <div className="rounded-lg border border-gray-700 bg-[#1C1C1E] p-6" data-testid="health-check-loading">
        <div className="flex items-center gap-3 mb-4">
          <Loader2 className="animate-spin text-[#007BFF]" size={20} />
          <span className="text-sm font-medium text-gray-300">
            Analyzing scenario readiness...
          </span>
        </div>

        {/* Progressive findings while loading */}
        {findings.length > 0 && (
          <div className="space-y-2 mt-4">
            {findings.map((finding, i) => (
              <FindingRow key={i} finding={finding} />
            ))}
          </div>
        )}
      </div>
    );
  }

  // No report yet and not analyzing
  if (!report && findings.length === 0) {
    return null;
  }

  // Full report
  const tier = report?.tier ?? "Not Ready";
  const tierCfg = TIER_CONFIG[tier];
  const TierIcon = tierCfg.icon;

  return (
    <div
      className="rounded-lg border border-gray-700 bg-[#1C1C1E] p-6 space-y-6"
      data-testid="health-check-report"
    >
      {/* Readiness score header */}
      {report && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-full ${tierCfg.color}/20`}
            >
              <span className="text-lg font-bold text-white">
                {report.readiness_score}
              </span>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-300">
                Readiness Score
              </p>
              <div className="flex items-center gap-1.5">
                <TierIcon size={14} className={tierCfg.textColor} />
                <span
                  className={`text-sm font-semibold ${tierCfg.textColor}`}
                  data-testid="tier-badge"
                >
                  {tier}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Per-agent prompt quality scores */}
      {report && report.prompt_quality_scores.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
            Agent Prompt Quality
          </h4>
          <div className="space-y-2">
            {report.prompt_quality_scores.map((agent, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg bg-gray-800/50 px-3 py-2"
                data-testid="agent-score"
              >
                <div>
                  <span className="text-sm text-gray-300">{agent.name}</span>
                  <span className="ml-2 text-xs text-gray-500">
                    ({agent.role})
                  </span>
                </div>
                <span
                  className={`text-sm font-semibold ${
                    agent.prompt_quality_score >= 80
                      ? "text-green-400"
                      : agent.prompt_quality_score >= 60
                        ? "text-yellow-400"
                        : "text-red-400"
                  }`}
                >
                  {agent.prompt_quality_score}/100
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Findings */}
      {findings.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
            Findings
          </h4>
          <div className="space-y-2">
            {findings.map((finding, i) => (
              <FindingRow key={i} finding={finding} />
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {report && report.recommendations.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
            Recommendations
          </h4>
          <ol className="list-decimal list-inside space-y-1.5">
            {report.recommendations.map((rec, i) => (
              <li
                key={i}
                className="text-sm text-gray-300"
                data-testid="recommendation"
              >
                {rec}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FindingRow({ finding }: { finding: HealthCheckFinding }) {
  const cfg = SEVERITY_CONFIG[finding.severity];
  const Icon = cfg.icon;

  return (
    <div
      className={`flex items-start gap-2 rounded-lg ${cfg.bgColor} px-3 py-2`}
      data-testid={`finding-${finding.severity}`}
    >
      <Icon size={16} className={`mt-0.5 shrink-0 ${cfg.color}`} />
      <div className="min-w-0">
        <span className="text-xs font-medium text-gray-400">
          {finding.check_name}
          {finding.agent_role && ` · ${finding.agent_role}`}
        </span>
        <p className="text-sm text-gray-300">{finding.message}</p>
      </div>
    </div>
  );
}
