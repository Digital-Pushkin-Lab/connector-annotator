# Аннотатор коннекторов

Эта ветка — вариант `main` для Google Colab (Python 3.12). Код тот же, что в
`main` (работает на Python 3.8+ и на Python 3.12 в Colab); отличаются только
инструкции по запуску ниже. Для локального запуска используйте ветку `main`.

## Установка

Автоматическая разметка линкеров использует движок из
[`linker_extraction`](https://github.com/Digital-Pushkin-Lab/connector-extractor),
подключённого как git submodule.

В ячейке Colab:

```python
!git clone --recurse-submodules -b colab-compatible \
    https://github.com/Digital-Pushkin-Lab/connector-annotator.git
%cd connector-annotator

!pip install -r requirements.txt
!python -c "import stanza; stanza.download('ru')"   # разовая загрузка модели

# Опционально: включает загрузку .doc (не .docx) на вкладке "Пакетная
# обработка" и при загрузке одиночного файла. Без этого .doc просто
# пропускается/показывает понятную ошибку — .txt/.docx/.xml работают и без него.
!apt-get install -y catdoc

!python3 gradio_app.py
```

`demo.launch(share=True)` уже включён, поэтому Gradio выдаст публичную
ссылку — по ней и открывайте интерфейс из Colab.
