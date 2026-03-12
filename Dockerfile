FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir arc-agi==0.9.2

COPY witness_grid.py .
COPY play_human.py .
COPY environment_files/ environment_files/
COPY levels/ levels/
COPY static/ static/
COPY assets/ assets/

EXPOSE 7860

CMD [\"python\", \"play_human.py\", \"7860\"]