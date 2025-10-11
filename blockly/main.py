from quart import Quart, request, jsonify, send_from_directory
import asyncio
import os

app = Quart(__name__, static_folder="static")

# Serve the main UI
@app.route("/")
async def blockly_index():
    return await send_from_directory(".", "index.html")

# Serve static files (Blockly JS, etc.) from /static
@app.route("/static/<path:filename>")
async def static_files(filename):
    return await send_from_directory("static", filename)

# Favicon
@app.route("/favicon.ico")
async def favicon():
    return await send_from_directory(".", "favicon.ico")

# Run user code endpoint
@app.route("/run", methods=["POST"])
async def run_code():
    data = await request.get_json()
    code = data.get("code", "")
    with open("user_code.py", "w") as f:
        f.write(code)
    try:
        proc = await asyncio.create_subprocess_exec(
            "python", "user_code.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        try:
            output, _ = await asyncio.wait_for(proc.communicate(), timeout=3)
            return jsonify({"output": output.decode()})
        except asyncio.TimeoutError:
            proc.kill()
            return jsonify({"output": "Execution timed out."}), 400
    except Exception as e:
        return jsonify({"output": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
