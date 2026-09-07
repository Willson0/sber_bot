import matplotlib.pyplot as plt
import matplotlib

matplotlib.use('Agg')  # Для работы без GUI
import io
from datetime import datetime


def create_pie_chart(subscriptions, total_yearly):
    """
    Создаёт круговую диаграмму расходов по подпискам
    Возвращает путь к сохранённому изображению
    """
    if not subscriptions:
        return None

    # Подготовка данных
    labels = []
    sizes = []
    colors = []

    # Цвета для диаграммы
    color_palette = [
        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
        '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#36A2EB'
    ]

    for i, sub in enumerate(subscriptions[:10]):  # Топ-10 подписок
        labels.append(sub['merchant'])
        sizes.append(sub['yearly_amount'])
        colors.append(color_palette[i % len(color_palette)])

    # Если есть остальные, добавляем как "Другие"
    if len(subscriptions) > 10:
        other_sum = sum(s['yearly_amount'] for s in subscriptions[10:])
        if other_sum > 0:
            labels.append('Другие')
            sizes.append(other_sum)
            colors.append('#95A5A6')

    # Создание диаграммы
    fig, ax = plt.subplots(figsize=(10, 8))

    # Круговая диаграмма
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct='%1.1f%%',
        startangle=90,
        pctdistance=0.85,
        textprops={'fontsize': 10}
    )

    # Стилизация процентов
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(9)

    # Делаем центр белым (пончик)
    centre_circle = plt.Circle((0, 0), 0.70, fc='white')
    fig.gca().add_artist(centre_circle)

    # Заголовок
    plt.title(
        f'Расходы на подписки за год\nВсего: {total_yearly:,.0f} ₽',
        fontsize=14,
        fontweight='bold',
        pad=20
    )

    # Сохраняем в буфер
    buf = io.BytesIO()
    plt.savefig(
        buf,
        format='png',
        dpi=150,
        bbox_inches='tight',
        facecolor='white'
    )
    buf.seek(0)

    # Путь для сохранения
    filename = f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    with open(filename, 'wb') as f:
        f.write(buf.getvalue())

    plt.close()

    return filename