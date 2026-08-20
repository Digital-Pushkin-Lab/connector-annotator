# Аннотатор коннекторов

Внимание: оптимизировано для Python3.8

## Установка

Автоматическая разметка линкеров и вводных слов использует движок из
[`linker_extraction`](https://github.com/Digital-Pushkin-Lab/connector-extractor),
подключённого как git submodule.

```bash
git clone --recurse-submodules https://github.com/Digital-Pushkin-Lab/connector-annotator.git
cd connector-annotator
# если репозиторий уже склонирован без --recurse-submodules:
git submodule update --init

pip install -r requirements.txt
python -c "import stanza; stanza.download('ru')"   # разовая загрузка модели

python3 gradio_app.py
```
