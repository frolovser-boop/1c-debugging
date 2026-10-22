# Dockerfile для автономного MCP-сервера отладки 1С (onec-debug)
FROM python:3.12-slim

WORKDIR /app

# Копируем проект и устанавливаем
COPY . /app
RUN pip install --no-cache-dir .

# Порт HTTP MCP сервера
EXPOSE 8080

# По умолчанию запускаем HTTP MCP сервер для сетевых и AI-агентов
ENTRYPOINT ["onec-debug"]
CMD ["mcp", "--http", "8080", "--host", "0.0.0.0"]
