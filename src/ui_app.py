from nicegui import ui, app


USERNAME = "admin"
PASSWORD = "1234"


def show_main_ui(out_queue):
    with ui.tabs() as tabs:
        ui.tab('h', label='Home', icon='home')
        ui.tab('s', label='Setup', icon='settings')
        ui.tab('a', label='About', icon='info')

    with ui.tab_panels(tabs, value='h').classes('w-full'):
        with ui.tab_panel('h'):
            ui.label('Main Content')
            temp_label = ui.label('Waiting for data...')

            def do_logout():
                app.storage.user.pop('logged_in', None)  # xoá trạng thái login
                ui.navigate.to('/login')

            ui.button('Logout', on_click=do_logout,
                      color='red').classes('ml-auto')

        with ui.tab_panel('s'):
            ui.label('Setting system')

        with ui.tab_panel('a'):
            ui.label('Infos')

    # Cập nhật data
    def update_ui():
        try:
            data = out_queue.get_nowait()
            if data.get('type') == 'temperature':
                text = f'{data["node_thermal"]}: {data["data_t"]} °C at {data["timestamp"]}'
                temp_label.text = text
        except Exception:
            pass

    ui.timer(0.5, update_ui)


def login_screen():
    with ui.card().classes('absolute-center w-96'):
        ui.label('🔐 Login').classes('text-xl font-bold mb-4')
        username = ui.input('Username').props('outlined').classes('mb-2')
        password = ui.input('Password').props(
            'outlined password').classes('mb-2')

        def attempt_login():
            if username.value == USERNAME and password.value == PASSWORD:
                app.storage.user['logged_in'] = True
                ui.navigate.to('/')
            else:
                ui.notify('❌ Wrong credentials', color='negative')

        ui.button('Login', on_click=attempt_login).classes('mt-2')


def register_pages(out_queue):
    @ui.page('/')
    def main_page():

        if not app.storage.user.get('logged_in'):
            ui.navigate.to('/login')  # ✅
        else:
            show_main_ui(out_queue)

    @ui.page('/login')
    def login_page():
        login_screen()
