import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

import AdminBroadcastPage from "@/app/admin/broadcast/page";

describe("AdminBroadcastPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders compose form with subject and body inputs", () => {
    render(<AdminBroadcastPage />);
    expect(screen.getByLabelText("Subject")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toBeInTheDocument();
  });

  it("renders Preview and Send buttons", () => {
    render(<AdminBroadcastPage />);
    expect(screen.getByText("Preview")).toBeInTheDocument();
    expect(screen.getByText("Send to All Users")).toBeInTheDocument();
  });

  it("disables buttons when fields are empty", () => {
    render(<AdminBroadcastPage />);
    expect(screen.getByText("Preview")).toBeDisabled();
    expect(screen.getByText("Send to All Users")).toBeDisabled();
  });

  it("enables buttons when both fields have content", () => {
    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Test" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hello" } });
    expect(screen.getByText("Preview")).not.toBeDisabled();
    expect(screen.getByText("Send to All Users")).not.toBeDisabled();
  });

  it("shows preview data after clicking Preview", async () => {
    const previewData = {
      recipients: ["a@b.com", "c@d.com"],
      total_recipients: 2,
      subject: "Test Subject",
      body_html: "<p>Hello world</p>",
      sender: "noreply@juntoai.com",
    };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(previewData),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Test Subject" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hello" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Preview"));
    });

    await waitFor(() => {
      expect(screen.getByText("Recipients")).toBeInTheDocument();
      expect(screen.getByText("2 users")).toBeInTheDocument();
      expect(screen.getByText("a@b.com")).toBeInTheDocument();
      expect(screen.getByText("c@d.com")).toBeInTheDocument();
      expect(screen.getByText("Email Preview")).toBeInTheDocument();
      expect(screen.getByText("Test Subject")).toBeInTheDocument();
    });
  });

  it("shows singular 'user' when total_recipients is 1", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        recipients: ["a@b.com"],
        total_recipients: 1,
        subject: "Hi",
        body_html: "<p>Hi</p>",
        sender: "noreply@juntoai.com",
      }),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hi" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Preview"));
    });

    await waitFor(() => {
      expect(screen.getByText("1 user")).toBeInTheDocument();
    });
  });

  it("shows empty recipients message when no active users", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        recipients: [],
        total_recipients: 0,
        subject: "Hi",
        body_html: "<p>Hi</p>",
        sender: "noreply@juntoai.com",
      }),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hi" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Preview"));
    });

    await waitFor(() => {
      expect(screen.getByText("No active users found.")).toBeInTheDocument();
    });
  });

  it("shows error on preview 401", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.reject(new Error("nope")),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hi" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Preview"));
    });

    await waitFor(() => {
      expect(screen.getByText("Session expired. Please log in again.")).toBeInTheDocument();
    });
  });

  it("shows error with detail on preview non-401 failure", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "Server broke" }),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hi" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Preview"));
    });

    await waitFor(() => {
      expect(screen.getByText("Server broke")).toBeInTheDocument();
    });
  });

  it("shows fallback error on preview non-JSON failure", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: () => Promise.reject(new Error("not json")),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hi" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Preview"));
    });

    await waitFor(() => {
      expect(screen.getByText("API error: 502")).toBeInTheDocument();
    });
  });

  it("shows confirmation dialog on Send click", () => {
    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hi" } });

    fireEvent.click(screen.getByText("Send to All Users"));
    expect(screen.getByText("Yes, send it")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("hides confirmation dialog on Cancel", () => {
    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hi" } });

    fireEvent.click(screen.getByText("Send to All Users"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByText("Yes, send it")).not.toBeInTheDocument();
  });

  it("sends broadcast and shows success result", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        total_users: 10,
        sent: 9,
        failed: 1,
        errors: ["failed@example.com: bounce"],
      }),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hello" } });

    fireEvent.click(screen.getByText("Send to All Users"));

    await act(async () => {
      fireEvent.click(screen.getByText("Yes, send it"));
    });

    await waitFor(() => {
      expect(screen.getByText(/Sent 9 \/ 10 emails/)).toBeInTheDocument();
      expect(screen.getByText(/1 failed/)).toBeInTheDocument();
      expect(screen.getByText("failed@example.com: bounce")).toBeInTheDocument();
    });
  });

  it("sends broadcast with zero failures", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        total_users: 5,
        sent: 5,
        failed: 0,
        errors: [],
      }),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hello" } });

    fireEvent.click(screen.getByText("Send to All Users"));

    await act(async () => {
      fireEvent.click(screen.getByText("Yes, send it"));
    });

    await waitFor(() => {
      expect(screen.getByText("Sent 5 / 5 emails")).toBeInTheDocument();
    });
  });

  it("shows error on send 401", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.reject(new Error("nope")),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hello" } });

    fireEvent.click(screen.getByText("Send to All Users"));

    await act(async () => {
      fireEvent.click(screen.getByText("Yes, send it"));
    });

    await waitFor(() => {
      expect(screen.getByText("Session expired. Please log in again.")).toBeInTheDocument();
    });
  });

  it("shows error with detail on send failure", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "SES quota exceeded" }),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Hi" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hello" } });

    fireEvent.click(screen.getByText("Send to All Users"));

    await act(async () => {
      fireEvent.click(screen.getByText("Yes, send it"));
    });

    await waitFor(() => {
      expect(screen.getByText("SES quota exceeded")).toBeInTheDocument();
    });
  });

  it("clears preview when subject changes", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        recipients: ["a@b.com"],
        total_recipients: 1,
        subject: "Old",
        body_html: "<p>Old</p>",
        sender: "noreply@juntoai.com",
      }),
    });

    render(<AdminBroadcastPage />);
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "Old" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Body" } });

    await act(async () => {
      fireEvent.click(screen.getByText("Preview"));
    });

    await waitFor(() => {
      expect(screen.getByText("Recipients")).toBeInTheDocument();
    });

    // Change subject — preview should clear
    fireEvent.change(screen.getByLabelText("Subject"), { target: { value: "New" } });
    expect(screen.queryByText("Recipients")).not.toBeInTheDocument();
  });
});
