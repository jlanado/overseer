FROM python:3.11-slim

# Docker CLI (for Deploy node's `docker compose` calls against the mounted socket)
# + git (for cloning) + curl + Node.js (Claude Code is an npm package).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Pin to a known-working version — an unpinned `npm install -g` here would
# make the Fixer node's exact behavior drift between rebuilds. Bump
# deliberately; check the Claude Code changelog when you do.
RUN npm install -g @anthropic-ai/claude-code@2.1.206

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
