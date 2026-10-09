"""Shared look for every macro window, so the same kind of control looks and behaves the same everywhere."""
import customtkinter as ctk

BLUE, BLUE_HOVER = "#0d6efd", "#0b5ed7"
GREEN, GREEN_HOVER = "#198754", "#157347"
GREY, GREY_HOVER = "#343a40", "#495057"
TEXT_DIM = "#adb5bd"

CARD = dict(fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
BTN = dict(height=30, font=("Arial", 12), fg_color="#495057", hover_color="#343a40", corner_radius=6)
BTN_BLUE = dict(height=30, font=("Arial", 12), fg_color=BLUE, hover_color=BLUE_HOVER, corner_radius=6)
TITLE_FONT = ("Arial", 16, "bold")


def big_toggle(parent, command):
    """The main ON/OFF switch of a page (Always Click OK, Event alerts...): full width and easy to hit."""
    return ctk.CTkButton(parent, text="", height=40, corner_radius=8, font=("Arial", 13, "bold"),
                         border_width=1, border_color="#495057", command=command)


def style_toggle(btn, on, name, icon_on="🔔", icon_off="🔕"):
    """Green with 'ON' when running, grey with 'OFF' when not, same wording on every page."""
    if on:
        btn.configure(text=f"{icon_on}  {name}: ON   (click to turn off)", fg_color=GREEN, hover_color=GREEN_HOVER,
                      text_color="#ffffff", border_color=GREEN)
    else:
        btn.configure(text=f"{icon_off}  {name}: OFF   (click to turn on)", fg_color=GREY, hover_color=GREY_HOVER,
                      text_color="#e9ecef", border_color="#495057")
