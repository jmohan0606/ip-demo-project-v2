export type ApiEnvelope<T> = { success: boolean; data: T; error?: string; message?: string; };
export type GraphHealth = { active_mode: "mcp" | "rest" | "mock" | "unavailable"; mcp_available: boolean; rest_available: boolean; mock_available: boolean; graph_name: string; strategy: string; };
