from __future__ import annotations

from .common import add_blank_slide, add_card, add_page_number, add_textbox, fill_background, rgb
from .layout_constants import CARDS_GRID, TITLE_BAND, cards_grid_positions
from ..schema import CardsGridSlide
from ..theme_loader import ThemeSpec


def render_cards_grid(prs, slide_data: CardsGridSlide, theme: ThemeSpec, log, slide_number: int, total_slides: int):
    slide = add_blank_slide(prs)
    fill_background(slide, theme)
    add_textbox(
        slide,
        left=TITLE_BAND.left,
        top=TITLE_BAND.top,
        width=TITLE_BAND.width,
        height=TITLE_BAND.height,
        text=slide_data.title,
        font_name=theme.fonts.title,
        font_size=theme.font_sizes.title,
        color_hex=theme.colors.primary,
        bold=True,
    )
    if slide_data.heading:
        add_textbox(
            slide,
            left=CARDS_GRID.heading_left,
            top=CARDS_GRID.heading_top,
            width=CARDS_GRID.heading_width,
            height=CARDS_GRID.heading_height,
            text=slide_data.heading,
            font_name=theme.fonts.body,
            font_size=theme.font_sizes.small + 1,
            color_hex=theme.colors.text_sub,
            bold=True,
        )

    for index, (card, position) in enumerate(zip(slide_data.cards, cards_grid_positions(len(slide_data.cards)))):
        left, top, width, height = position
        shape = add_card(slide, left, top, width, height, theme)
        if index % 2 == 0:
            shape.fill.fore_color.rgb = rgb(theme.colors.bg)
        add_textbox(
            slide,
            left=left + CARDS_GRID.card_title_left_padding,
            top=top + CARDS_GRID.card_title_top_padding,
            width=width - CARDS_GRID.card_title_left_padding * 2,
            height=CARDS_GRID.card_title_height,
            text=card.title,
            font_name=theme.fonts.title,
            font_size=theme.font_sizes.subtitle,
            color_hex=theme.colors.secondary,
            bold=True,
        )
        if card.body:
            add_textbox(
                slide,
                left=left + CARDS_GRID.card_title_left_padding,
                top=top + CARDS_GRID.card_body_top_offset,
                width=width - CARDS_GRID.card_title_left_padding * 2,
                height=height - CARDS_GRID.card_body_bottom_padding,
                text=card.body,
                font_name=theme.fonts.body,
                font_size=theme.font_sizes.small + 1,
                color_hex=theme.colors.text_main,
            )

    log.info(f"{slide_data.slide_id}: rendered semantic cards grid layout.")
    add_page_number(slide, slide_number, total_slides, theme)
    return slide
