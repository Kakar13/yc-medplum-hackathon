FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Verify installation
RUN python -c "from harness.agent import load_config; print(load_config())"
RUN python -c "from harness.middleware import haarf_middleware; print('middleware OK')"
RUN python -c "from harness.tools import TOOL_SCHEMAS; print(f'{len(TOOL_SCHEMAS)} tools loaded')"

# Default: show help
CMD ["python", "runner.py", "--help"]
