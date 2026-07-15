#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerGetAuthTokenTool } from "./tools/get-auth-token.js";
import { registerQueryProjectsTool } from "./tools/query-projects.js";
import { registerQueryTestVersionsTool } from "./tools/query-test-versions.js";
import { registerExportTestCasesTool } from "./tools/export-test-cases.js";
import { registerSearchTestCasesTool } from "./tools/search-test-cases.js";
import { registerGetCaseContentTool } from "./tools/get-case-content.js";
import { registerEditCaseContentTool } from "./tools/edit-case-content.js";
import { registerSwitchEnvironmentTool } from "./tools/switch-environment.js";
import { registerListAvailableEnvironmentsTool } from "./tools/list-available-environments.js";
import { registerSearchRequirementsTool } from "./tools/search-requirements.js";
const server = new McpServer({
    name: "taas-mcp",
    version: "0.1.0",
});
// Register get auth token tool
registerGetAuthTokenTool(server);
// Register query projects tool
registerQueryProjectsTool(server);
// Register query test versions tool
registerQueryTestVersionsTool(server);
// Register export test cases tool
registerExportTestCasesTool(server);
// Register search test cases tool
registerSearchTestCasesTool(server);
// Register get case content tool
registerGetCaseContentTool(server);
// Register edit case content tool
registerEditCaseContentTool(server);
// Register switch environment tool
registerSwitchEnvironmentTool(server);
// Register list available environments tool
registerListAvailableEnvironmentsTool(server);
// Register search requirements tool
registerSearchRequirementsTool(server);
// Start the server
async function main() {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("Taas MCP server running on stdio");
}
main().catch((error) => {
    console.error("Server error:", error);
    process.exit(1);
});
