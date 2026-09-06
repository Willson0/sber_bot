"""
Генерация красивого графика истории списаний по подписке.
matplotlib + backend 'Agg' — рендеринг без дисплея, для серверного бота.
"""
import io
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
import numpy as np


# Палитра
COLOR_BAR_TOP = '#7C9EFF'
COLOR_BAR_BOTTOM = '#3E63DD'
COLOR_AVG_LINE = '#FF6B6B'
COLOR_GRID = '#E5E7EB'
COLOR_TEXT = '#1F2937'
COLOR_BG = '#FFFFFF'


def _parse_date(d: str):
    try:
        return datetime.strptime(d, '%d.%m.%Y')
    except Exception:
        return None


def _gradient_bar(ax, x, height, width, top_color, bottom_color):
    """Рисует один столбец с вертикальным градиентом вместо плоского цвета."""
    n = 100
    gradient = np.linspace(0, 1, n).reshape(n, 1)

    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list('bar_grad', [bottom_color, top_color])

    ax.imshow(
        gradient,
        extent=[x - width / 2, x + width / 2, 0, height],
        aspect='auto',
        cmap=cmap,
        origin='lower',
        zorder=2,
    )


def generate_subscription_chart(transactions: list[dict], subscription_name: str) -> io.BytesIO | None:
    """
    Строит красивый график истории списаний по подписке.

    - 2+ точек — столбчатая диаграмма с градиентом, средней линией
      и подписями сумм над каждым столбцом.
    - 1 точка — отдельное аккуратное оформление для единственного
      списания (не молчим, а показываем красиво).
    - 0 точек — None (действительно нечего рисовать).
    """
    points = []
    for t in transactions:
        date = _parse_date(t.get('date', ''))
        amount = t.get('amount')
        if date is None or amount is None:
            continue
        points.append((date, abs(amount)))

    if not points:
        return None

    points.sort(key=lambda p: p[0])
    dates = [p[0] for p in points]
    amounts = [p[1] for p in points]

    plt.rcParams['font.family'] = 'DejaVu Sans'  # кириллица из коробки

    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=180)
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    if len(points) == 1:
        # ── Единственное списание ────────────────────────────────
        x = dates[0]
        height = amounts[0]
        width = timedelta(days=6)

        _gradient_bar(ax, mdates.date2num(x), height,
                       mdates.date2num(x + width) - mdates.date2num(x - width),
                       COLOR_BAR_TOP, COLOR_BAR_BOTTOM)

        ax.set_xlim(mdates.date2num(x - timedelta(days=20)),
                     mdates.date2num(x + timedelta(days=20)))
        ax.set_ylim(0, height * 1.35)

        ax.annotate(
            f'{height:,.0f} ₽'.replace(',', ' '),
            xy=(x, height), xytext=(0, 10), textcoords='offset points',
            ha='center', fontsize=12, fontweight='bold', color=COLOR_TEXT,
        )
        ax.annotate(
            '⚠️ Найдено только одно списание',
            xy=(0.5, -0.22), xycoords='axes fraction',
            ha='center', fontsize=9, color='#9CA3AF',
        )
    else:
        # ── Несколько списаний — полноценная динамика ───────────
        x_nums = mdates.date2num(dates)
        width = max((x_nums[-1] - x_nums[0]) / max(len(x_nums) * 2.2, 1), 3)

        for xn, h in zip(x_nums, amounts):
            _gradient_bar(ax, xn, h, width, COLOR_BAR_TOP, COLOR_BAR_BOTTOM)

        avg = sum(amounts) / len(amounts)
        ax.axhline(
            avg, color=COLOR_AVG_LINE, linestyle='--', linewidth=1.6,
            zorder=3, label=f'Средний платёж: {avg:,.0f} ₽'.replace(',', ' '),
        )

        for xn, h in zip(x_nums, amounts):
            ax.annotate(
                f'{h:,.0f}'.replace(',', ' '),
                xy=(xn, h), xytext=(0, 6), textcoords='offset points',
                ha='center', fontsize=9, color=COLOR_TEXT, fontweight='medium',
                zorder=4,
            )

        pad = (x_nums[-1] - x_nums[0]) * 0.08 if len(x_nums) > 1 else 5
        ax.set_xlim(x_nums[0] - pad - width, x_nums[-1] + pad + width)
        ax.set_ylim(0, max(amounts) * 1.25)

        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%y'))
        fig.autofmt_xdate(rotation=25, ha='right')

        legend = ax.legend(
            loc='upper left', fontsize=9.5, frameon=False,
            handlelength=1.8, handletextpad=0.6,
        )
        for text in legend.get_texts():
            text.set_color(COLOR_TEXT)

    # ── Общее оформление ──────────────────────────────────────────
    ax.set_title(
        f'📊 История списаний: {subscription_name}',
        fontsize=13.5, fontweight='bold', color=COLOR_TEXT, pad=14,
    )
    ax.set_ylabel('Сумма, ₽', fontsize=10, color='#6B7280')

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#D1D5DB')
    ax.spines['bottom'].set_color('#D1D5DB')

    ax.grid(axis='y', linestyle=':', linewidth=0.8, color=COLOR_GRID, zorder=0)
    ax.tick_params(colors='#6B7280', labelsize=9)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
