import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import OutcomeReceipt from "@/components/glassbox/OutcomeReceipt";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

beforeEach(() => {
  mockPush.mockClear();
});

const defaultProps = {
  dealStatus: "Agreed" as const,
  finalSummary: {
    outcome: "Deal closed successfully",
    current_offer: 500000,
    turns_completed: 6,
    total_warnings: 1,
  },
  elapsedTimeMs: 12500,
  scenarioOutcomeReceipt: {
    equivalent_human_time: "2-4 weeks",
    process_label: "Enterprise SaaS negotiation",
  },
  scenarioId: "talent_war",
};

describe("OutcomeReceipt", () => {
  it("renders Agreed status with structured deal data and success styling", () => {
    render(<OutcomeReceipt {...defaultProps} />);

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Agreed");

    const content = screen.getByTestId("outcome-content");
    expect(content).toHaveTextContent("Deal closed successfully");
    expect(content).toHaveTextContent("Final Price:");
    expect(content).toHaveTextContent("€500,000");
    expect(content).toHaveTextContent("Turns: 6");
    expect(content).toHaveTextContent("Warnings: 1");

    // Success styling — green border
    const card = screen.getByTestId("outcome-heading").closest("div.rounded-lg");
    expect(card?.className).toContain("border-green-500");
    expect(card?.className).toContain("bg-green-50");
  });

  it("renders Agreed status without optional fields when absent", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        finalSummary={{}}
      />,
    );

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Agreed");
    const content = screen.getByTestId("outcome-content");
    expect(content).not.toHaveTextContent("Final Price:");
    expect(content).not.toHaveTextContent("Turns:");
    expect(content).not.toHaveTextContent("Warnings:");
  });

  it("renders Blocked status with blocked_by, reason, and warning styling", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        dealStatus="Blocked"
        finalSummary={{
          blocked_by: "EU Regulator",
          reason: "Regulator blocked the deal",
          current_offer: 300000,
          total_warnings: 3,
        }}
      />,
    );

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Deal Blocked");

    const content = screen.getByTestId("outcome-content");
    expect(content).toHaveTextContent("Blocked by: EU Regulator");
    expect(content).toHaveTextContent("Regulator blocked the deal");
    expect(content).toHaveTextContent("Last Offer: €300,000");
    expect(content).toHaveTextContent("Total Warnings: 3");

    const card = screen.getByTestId("outcome-heading").closest("div.rounded-lg");
    expect(card?.className).toContain("border-yellow-500");
    expect(card?.className).toContain("bg-yellow-50");
  });

  it("renders Blocked status without optional blocked_by field", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        dealStatus="Blocked"
        finalSummary={{ reason: "Compliance violation" }}
      />,
    );

    const content = screen.getByTestId("outcome-content");
    expect(content).not.toHaveTextContent("Blocked by:");
    expect(content).toHaveTextContent("Compliance violation");
  });

  it("renders Failed status with default max turns message", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        dealStatus="Failed"
        finalSummary={{}}
      />,
    );

    expect(screen.getByTestId("outcome-heading")).toHaveTextContent("Negotiation Failed");
    expect(
      screen.getByText("Negotiation reached maximum turns without agreement"),
    ).toBeInTheDocument();

    const card = screen.getByTestId("outcome-heading").closest("div.rounded-lg");
    expect(card?.className).toContain("border-gray-400");
    expect(card?.className).toContain("bg-gray-50");
  });

  it("renders Failed status with custom reason when provided", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        dealStatus="Failed"
        finalSummary={{ reason: "Parties walked away", current_offer: 100000, total_warnings: 2 }}
      />,
    );

    const content = screen.getByTestId("outcome-content");
    expect(content).toHaveTextContent("Parties walked away");
    expect(content).not.toHaveTextContent("Negotiation reached maximum turns");
    expect(content).toHaveTextContent("Last Offer: €100,000");
    expect(content).toHaveTextContent("Warnings: 2");
  });

  it("displays both measured and estimated ROI metric groups", () => {
    render(<OutcomeReceipt {...defaultProps} />);

    // Measured
    const measured = screen.getByTestId("measured-metrics");
    expect(measured).toHaveTextContent("Time Elapsed: 13s");

    // Estimated
    const estimated = screen.getByTestId("estimated-metrics");
    expect(estimated).toHaveTextContent("Industry Estimate");
    expect(estimated).toHaveTextContent("Equivalent Human Time: 2-4 weeks");
    expect(estimated).toHaveTextContent("Enterprise SaaS negotiation");
  });

  it("displays ai_tokens_used when present in finalSummary", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        finalSummary={{ ...defaultProps.finalSummary, ai_tokens_used: 12345 }}
      />,
    );

    const measured = screen.getByTestId("measured-metrics");
    expect(measured).toHaveTextContent("AI Tokens: 12,345");
  });

  it("hides estimated metrics when scenarioOutcomeReceipt is null", () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        scenarioOutcomeReceipt={null}
      />,
    );

    expect(screen.queryByTestId("estimated-metrics")).not.toBeInTheDocument();
  });

  it('"Run Another Scenario" navigates to /arena', () => {
    render(<OutcomeReceipt {...defaultProps} />);

    fireEvent.click(screen.getByTestId("run-another-btn"));
    expect(mockPush).toHaveBeenCalledWith("/arena");
  });

  it('"Reset with Different Variables" navigates to /arena?scenario={id}', () => {
    render(<OutcomeReceipt {...defaultProps} />);

    fireEvent.click(screen.getByTestId("reset-variables-btn"));
    expect(mockPush).toHaveBeenCalledWith("/arena?scenario=talent_war");
  });

  it('"Reset with Different Variables" navigates to /arena when scenarioId is null', () => {
    render(
      <OutcomeReceipt
        {...defaultProps}
        scenarioId={null}
      />,
    );

    fireEvent.click(screen.getByTestId("reset-variables-btn"));
    expect(mockPush).toHaveBeenCalledWith("/arena");
  });

  // -------------------------------------------------------------------------
  // Evaluation section (spec 170_negotiation-evaluator)
  // -------------------------------------------------------------------------

  describe("Evaluation section", () => {
    const baseEvaluation = {
      overall_score: 7,
      dimensions: {
        fairness: 7,
        mutual_respect: 8,
        value_creation: 6,
        satisfaction: 7,
      },
      verdict: "A solid deal both parties can live with.",
      participant_interviews: [
        {
          role: "Buyer",
          satisfaction_rating: 8,
          felt_respected: true,
          is_win_win: true,
          criticism: "Would have liked a lower price.",
        },
        {
          role: "Seller",
          satisfaction_rating: 6,
          felt_respected: true,
          is_win_win: true,
          criticism: "",
        },
      ],
    };

    it("does not render evaluation section when evaluation is absent", () => {
      render(<OutcomeReceipt {...defaultProps} />);
      expect(screen.queryByTestId("evaluation-section")).not.toBeInTheDocument();
    });

    it("does not render evaluation section when evaluation is null", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{ ...defaultProps.finalSummary, evaluation: null }}
        />,
      );
      expect(screen.queryByTestId("evaluation-section")).not.toBeInTheDocument();
    });

    it("renders overall score, dimensions, verdict, and participants when evaluation is present", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{ ...defaultProps.finalSummary, evaluation: baseEvaluation }}
        />,
      );

      // Section heading
      expect(screen.getByTestId("evaluation-section")).toBeInTheDocument();

      // Overall score
      const scoreBlock = screen.getByTestId("evaluation-score");
      expect(scoreBlock).toHaveTextContent("7");
      expect(scoreBlock).toHaveTextContent("/ 10");

      // Dimensions — 4 rows with name + value
      const dims = screen.getByTestId("evaluation-dimensions");
      expect(dims).toHaveTextContent("fairness");
      expect(dims).toHaveTextContent("7/10");
      expect(dims).toHaveTextContent("mutual respect");
      expect(dims).toHaveTextContent("8/10");
      expect(dims).toHaveTextContent("value creation");
      expect(dims).toHaveTextContent("6/10");
      expect(dims).toHaveTextContent("satisfaction");

      // Verdict
      expect(screen.getByTestId("evaluation-verdict")).toHaveTextContent(
        "A solid deal both parties can live with.",
      );

      // Participants
      const participants = screen.getByTestId("evaluation-participants");
      expect(participants).toHaveTextContent("Buyer");
      expect(participants).toHaveTextContent("8/10");
      expect(participants).toHaveTextContent("Seller");
      expect(participants).toHaveTextContent("6/10");
      expect(participants).toHaveTextContent("Would have liked a lower price.");
    });

    it("applies emerald color for overall score >= 9", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: { ...baseEvaluation, overall_score: 9 },
          }}
        />,
      );
      const scoreValue = screen
        .getByTestId("evaluation-score")
        .querySelector("span");
      expect(scoreValue?.className).toContain("text-emerald-400");
    });

    it("applies green color for overall score 7-8", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: { ...baseEvaluation, overall_score: 7 },
          }}
        />,
      );
      const scoreValue = screen
        .getByTestId("evaluation-score")
        .querySelector("span");
      expect(scoreValue?.className).toContain("text-green-500");
    });

    it("applies amber color for overall score 4-6", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: { ...baseEvaluation, overall_score: 5 },
          }}
        />,
      );
      const scoreValue = screen
        .getByTestId("evaluation-score")
        .querySelector("span");
      expect(scoreValue?.className).toContain("text-amber-500");
    });

    it("applies red color for overall score below 4", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: { ...baseEvaluation, overall_score: 2 },
          }}
        />,
      );
      const scoreValue = screen
        .getByTestId("evaluation-score")
        .querySelector("span");
      expect(scoreValue?.className).toContain("text-red-500");
    });

    it("renders score as 0 when overall_score is missing", () => {
      const { dimensions, verdict, participant_interviews } = baseEvaluation;
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: { dimensions, verdict, participant_interviews },
          }}
        />,
      );
      expect(screen.getByTestId("evaluation-score")).toHaveTextContent("0");
    });

    it("does not render dimensions grid when dimensions is absent", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: {
              overall_score: 7,
              verdict: "No dimensions provided.",
              participant_interviews: [],
            },
          }}
        />,
      );
      expect(screen.queryByTestId("evaluation-dimensions")).not.toBeInTheDocument();
    });

    it("does not render verdict when verdict is absent", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: {
              overall_score: 7,
              dimensions: baseEvaluation.dimensions,
              participant_interviews: [],
            },
          }}
        />,
      );
      expect(screen.queryByTestId("evaluation-verdict")).not.toBeInTheDocument();
    });

    it("does not render participants list when interviews array is empty", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: {
              ...baseEvaluation,
              participant_interviews: [],
            },
          }}
        />,
      );
      expect(screen.queryByTestId("evaluation-participants")).not.toBeInTheDocument();
    });

    it("does not render participants list when interviews is undefined", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: {
              overall_score: 7,
              dimensions: baseEvaluation.dimensions,
              verdict: "No interviews.",
            },
          }}
        />,
      );
      expect(screen.queryByTestId("evaluation-participants")).not.toBeInTheDocument();
    });

    it("applies correct color coding per participant satisfaction rating", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: {
              ...baseEvaluation,
              participant_interviews: [
                { role: "HighSat", satisfaction_rating: 9, criticism: "" },
                { role: "MidSat", satisfaction_rating: 5, criticism: "" },
                { role: "LowSat", satisfaction_rating: 2, criticism: "" },
              ],
            },
          }}
        />,
      );
      const participants = screen.getByTestId("evaluation-participants");
      const spans = participants.querySelectorAll("span.font-semibold");
      expect(spans[0].className).toContain("text-green-600");
      expect(spans[1].className).toContain("text-amber-600");
      expect(spans[2].className).toContain("text-red-600");
    });

    it("applies correct color coding per dimension value", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: {
              ...baseEvaluation,
              dimensions: { high: 9, mid: 5, low: 2 },
            },
          }}
        />,
      );
      // The fill bars have inline style width (the track has no style attr)
      const bars = Array.from(
        screen
          .getByTestId("evaluation-dimensions")
          .querySelectorAll<HTMLDivElement>("div.h-2.rounded-full"),
      ).filter((el) => el.style.width !== "");
      expect(bars[0].className).toContain("bg-green-500");
      expect(bars[1].className).toContain("bg-amber-400");
      expect(bars[2].className).toContain("bg-red-400");
    });

    it("renders full criticism text without truncation", () => {
      const longCriticism = "The process felt rushed and I would have preferred more time to consider the final terms before committing.";
      render(
        <OutcomeReceipt
          {...defaultProps}
          finalSummary={{
            ...defaultProps.finalSummary,
            evaluation: {
              ...baseEvaluation,
              participant_interviews: [
                { role: "Verbose", satisfaction_rating: 5, criticism: longCriticism },
              ],
            },
          }}
        />,
      );
      const participants = screen.getByTestId("evaluation-participants");
      expect(participants).toHaveTextContent(longCriticism);
    });
  });

  // -------------------------------------------------------------------------
  // What-If Prompt Cards (spec 260_what-if-prompts)
  // -------------------------------------------------------------------------

  describe("What-If Prompt Cards", () => {
    const toggles = [
      { id: "competing_offer", label: "Competing Offer", target_agent_role: "candidate" },
      { id: "deadline_pressure", label: "Deadline Pressure", target_agent_role: "recruiter" },
    ];

    const agents = [
      { name: "Alex", role: "candidate", goals: [], model_id: "gemini-2.5-flash", type: "negotiator" as const },
      { name: "Jordan", role: "recruiter", goals: [], model_id: "gemini-2.5-flash", type: "negotiator" as const },
    ];

    it("renders prompt cards when toggles + activeToggleIds + agents provided", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          toggles={toggles}
          activeToggleIds={[]}
          agents={agents}
        />,
      );

      expect(screen.getByTestId("what-if-prompts")).toBeInTheDocument();
      expect(screen.getByTestId("what-if-card-0")).toBeInTheDocument();
      expect(screen.getByTestId("what-if-card-1")).toBeInTheDocument();
      // "Run Another Scenario" should NOT be present when prompts are shown
      expect(screen.queryByTestId("run-another-btn")).not.toBeInTheDocument();
    });

    it('retains "Reset with Different Variables" button alongside cards', () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          toggles={toggles}
          activeToggleIds={[]}
          agents={agents}
        />,
      );

      expect(screen.getByTestId("what-if-prompts")).toBeInTheDocument();
      expect(screen.getByTestId("reset-variables-btn")).toBeInTheDocument();
    });

    it('falls back to "Run Another Scenario" when toggles prop not provided', () => {
      render(<OutcomeReceipt {...defaultProps} />);

      expect(screen.getByTestId("run-another-btn")).toBeInTheDocument();
      expect(screen.queryByTestId("what-if-prompts")).not.toBeInTheDocument();
    });

    it('falls back when toggles array is empty', () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          toggles={[]}
          activeToggleIds={[]}
          agents={agents}
        />,
      );

      expect(screen.getByTestId("run-another-btn")).toBeInTheDocument();
      expect(screen.queryByTestId("what-if-prompts")).not.toBeInTheDocument();
    });

    it("card click navigates to correct deep-link URL", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          toggles={toggles}
          activeToggleIds={[]}
          agents={agents}
        />,
      );

      fireEvent.click(screen.getByTestId("what-if-card-0"));
      expect(mockPush).toHaveBeenCalledWith(
        expect.stringContaining("/arena?scenario=talent_war&toggles="),
      );
    });
  });

  // -------------------------------------------------------------------------
  // Advice "Try This" Button (spec 260_what-if-prompts, Requirement 6)
  // -------------------------------------------------------------------------

  describe("Advice Try This Button", () => {
    const blockedWithAdvice = {
      blocked_by: "EU Regulator",
      reason: "Compliance issue",
      advice: [
        {
          agent_role: "recruiter",
          issue: "Too aggressive on salary",
          suggested_prompt: "Be more flexible on compensation",
        },
        {
          agent_role: "candidate",
          issue: "Unrealistic expectations",
          suggested_prompt: "Lower your initial ask by 10%",
        },
      ],
    };

    it('renders "Try This" button for each advice item with non-empty suggested_prompt', () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          dealStatus="Blocked"
          finalSummary={blockedWithAdvice}
        />,
      );

      expect(screen.getByTestId("try-this-btn-0")).toBeInTheDocument();
      expect(screen.getByTestId("try-this-btn-1")).toBeInTheDocument();
      expect(screen.getByTestId("try-this-btn-0")).toHaveTextContent("Try This");
      expect(screen.getByTestId("try-this-btn-1")).toHaveTextContent("Try This");
    });

    it('does not render "Try This" button when suggested_prompt is empty', () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          dealStatus="Blocked"
          finalSummary={{
            blocked_by: "Regulator",
            advice: [
              { agent_role: "recruiter", issue: "Problem", suggested_prompt: "" },
              { agent_role: "candidate", issue: "Other", suggested_prompt: "   " },
            ],
          }}
        />,
      );

      expect(screen.queryByTestId("try-this-btn-0")).not.toBeInTheDocument();
      expect(screen.queryByTestId("try-this-btn-1")).not.toBeInTheDocument();
    });

    it('does not render "Try This" button when suggested_prompt is missing', () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          dealStatus="Blocked"
          finalSummary={{
            blocked_by: "Regulator",
            advice: [
              { agent_role: "recruiter", issue: "Problem" },
            ],
          }}
        />,
      );

      expect(screen.queryByTestId("try-this-btn-0")).not.toBeInTheDocument();
    });

    it('does not render "Try This" button when scenarioId is null', () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          dealStatus="Blocked"
          finalSummary={blockedWithAdvice}
          scenarioId={null}
        />,
      );

      expect(screen.getByTestId("block-advice")).toBeInTheDocument();
      expect(screen.queryByTestId("try-this-btn-0")).not.toBeInTheDocument();
      expect(screen.queryByTestId("try-this-btn-1")).not.toBeInTheDocument();
    });

    it("click navigates to URL containing scenario param and Base64-encoded customPrompts param", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          dealStatus="Blocked"
          finalSummary={blockedWithAdvice}
        />,
      );

      fireEvent.click(screen.getByTestId("try-this-btn-0"));

      expect(mockPush).toHaveBeenCalledTimes(1);
      const url = mockPush.mock.calls[0][0] as string;

      // Must contain scenario param
      expect(url).toContain("/arena?scenario=talent_war");
      // Must contain customPrompts param
      expect(url).toContain("customPrompts=");
    });

    it("decoded customPrompts param contains correct agent_role → suggested_prompt mapping", () => {
      render(
        <OutcomeReceipt
          {...defaultProps}
          dealStatus="Blocked"
          finalSummary={blockedWithAdvice}
        />,
      );

      fireEvent.click(screen.getByTestId("try-this-btn-0"));

      const url = mockPush.mock.calls[0][0] as string;
      const urlObj = new URL(url, "http://localhost");
      const encoded = urlObj.searchParams.get("customPrompts")!;
      const decoded: Record<string, string> = JSON.parse(atob(decodeURIComponent(encoded)));

      expect(decoded).toEqual({ recruiter: "Be more flexible on compensation" });
    });
  });
});
