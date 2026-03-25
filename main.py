import flet as ft
from accounts import AccountsManager
from projects import ProjectsManager
from expenses import ExpensesManager
from dashboard import DashboardManager


def main(page: ft.Page):
    page.title = "Retro activities tracker"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.width = 1200
    page.height = 900

    def update_content_area(new_content: ft.Container):
        content_area.content = new_content
        page.update()

    accounts_manager = AccountsManager(page, update_content_area)
    projects_manager = ProjectsManager(page, update_content_area, accounts_manager)
    expenses_manager = ExpensesManager(page, update_content_area, accounts_manager, projects_manager)
    projects_manager.set_expenses_manager(expenses_manager)

    dashboard_manager = DashboardManager(page, accounts_manager, projects_manager, expenses_manager)

    def on_menu_click(e: ft.ControlEvent):
        for item in menu_items:
            item.bgcolor = None
            if isinstance(item.content, ft.Row) and len(item.content.controls) > 1 and isinstance(item.content.controls[1], ft.Text):
                item.content.controls[1].color = None

        e.control.bgcolor = ft.Colors.BLUE_700
        if isinstance(e.control.content, ft.Row) and len(e.control.content.controls) > 1 and isinstance(e.control.content.controls[1], ft.Text):
            e.control.content.controls[1].color = ft.Colors.WHITE

        if e.control.data == "dashboard":
            content_area.content = dashboard_manager.get_view()
        elif e.control.data == "wallets":
            content_area.content = accounts_manager.get_view()
        elif e.control.data == "projects":
            content_area.content = projects_manager.get_view()
        elif e.control.data == "expenses":
            content_area.content = expenses_manager.get_view()

        page.update()

    menu_items = [
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.DASHBOARD, size=20, color=ft.Colors.PURPLE_400),
                ft.Text("Dashboard", size=16),
            ], spacing=10),
            data="dashboard",
            padding=15,
            border_radius=10,
            on_click=on_menu_click,
            alignment=ft.Alignment.CENTER_LEFT,
        ),
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, size=20, color=ft.Colors.BLUE_400),
                ft.Text("Wallets", size=16),
            ], spacing=10),
            data="wallets",
            padding=15,
            border_radius=10,
            on_click=on_menu_click,
            alignment=ft.Alignment.CENTER_LEFT,
        ),
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.FOLDER_OUTLINED, size=20, color=ft.Colors.GREEN_400),
                ft.Text("Projects", size=16),
            ], spacing=10),
            data="projects",
            padding=15,
            border_radius=10,
            on_click=on_menu_click,
            alignment=ft.Alignment.CENTER_LEFT,
        ),
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ATTACH_MONEY, size=20, color=ft.Colors.ORANGE_400),
                ft.Text("Expenses", size=16),
            ], spacing=10),
            data="expenses",
            padding=15,
            border_radius=10,
            on_click=on_menu_click,
            alignment=ft.Alignment.CENTER_LEFT,
        ),
    ]

    content_area = ft.Container(
        content=dashboard_manager.get_view(),
        expand=True
    )

    menu_items[0].bgcolor = ft.Colors.BLUE_700
    if isinstance(menu_items[0].content, ft.Row) and len(menu_items[0].content.controls) > 1:
        menu_items[0].content.controls[1].color = ft.Colors.WHITE

    page.add(
        ft.Row([
            ft.Container(
                content=ft.Column(menu_items, spacing=5),
                width=200,
                padding=10,
                border=ft.Border.all(1, ft.Colors.GREY_800)
            ),
            content_area
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
    )

    page.update()


if __name__ == "__main__":
    ft.run(main)