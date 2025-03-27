from echoai.prompt import PromptLoader

mcp_prompt = PromptLoader.get_instance().render_template(
    "partials/mcp.prompt",
    mcp_servers=[{
        "name": "weather"
    }],
    mcp_server_path="/home/mcp/servers/weather",
    mcp_servers_setting_filepath="/home/mcp/servers/weather/server.properties",
)

print(mcp_prompt)