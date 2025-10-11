from quart import Quart, request, jsonify, send_from_directory
import asyncio

app = Quart(__name__, static_folder='/blockly/demos/code')

@app.route("/")
async def blockly_index():
    return await send_from_directory(app.static_folder, 'index.html')

@app.route("/<path:path>")
async def serve_static(path):
    return await send_from_directory(app.static_folder, path)

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
    app.run(host="0.0.0.0", port=5000)