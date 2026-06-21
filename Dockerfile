# Playwright এর official image - Chromium + সব system dependency প্রি-ইনস্টলড
# এটা Railway/যেকোনো Docker host এ ঝামেলামুক্ত deploy দেয়
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

# Dependencies install (layer caching এর জন্য আগে copy)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browser বেস image এ আগে থেকেই আছে, তবুও নিশ্চিত করার জন্য
RUN python -m playwright install chromium

# অ্যাপ কোড কপি
COPY app/ ./app/
COPY templates/ ./templates/

# Railway PORT env var দিয়ে পোর্ট বরাদ্দ করে
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
