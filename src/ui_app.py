from nicegui import ui, app
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from config_loader import load_config, DEFAULT_CONFIG_PATH


USERNAME = "admin"
PASSWORD = "1234"


class CameraEditor:
    """Camera configuration editor with data binding."""
    
    def __init__(self, camera_data: Dict[str, Any], cam_idx: int, on_save_callback=None):
        self.camera_data = camera_data
        self.cam_idx = cam_idx
        self.on_save_callback = on_save_callback
        
        # Input references for data binding
        self.inputs = {}
    
    def render(self):
        """Render camera editor UI."""
        with ui.expansion(
            f"📹 {self.camera_data.get('camera_name', f'Camera {self.cam_idx+1}')}", 
            icon='videocam'
        ).classes('w-full mb-4') as expansion:
            with ui.card().classes('w-full'):
                self._render_basic_info()
                ui.separator().classes('my-4')
                self._render_presets()
                ui.separator().classes('my-4')
                self._render_urls()
                ui.separator().classes('my-4')
                self._render_actions()
    
    def _render_basic_info(self):
        """Render basic camera information section."""
        ui.label('Basic Information').classes('text-subtitle1 font-bold mb-2')
        
        with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
            self.inputs['camera_name'] = ui.input(
                'Camera Name', 
                value=self.camera_data.get('camera_name', '')
            ).classes('w-full').props('outlined')
            
            self.inputs['camera_ip'] = ui.input(
                'Camera IP', 
                value=self.camera_data.get('camera_ip', '')
            ).classes('w-full').props('outlined')
            
            self.inputs['username'] = ui.input(
                'Username', 
                value=self.camera_data.get('username', '')
            ).classes('w-full').props('outlined')
            
            self.inputs['password'] = ui.input(
                'Password', 
                value=self.camera_data.get('password', ''),
                password=True,
                password_toggle_button=True
            ).classes('w-full').props('outlined')
        
        with ui.grid(columns=3).classes('w-full gap-4 mb-4'):
            self.inputs['interval_seconds'] = ui.number(
                'Interval (s)', 
                value=self.camera_data.get('interval_seconds', 30),
                min=1, max=300
            ).classes('w-full').props('outlined')
            
            self.inputs['timeout_seconds'] = ui.number(
                'Timeout (s)', 
                value=self.camera_data.get('timeout_seconds', 5),
                min=1, max=30
            ).classes('w-full').props('outlined')
            
            self.inputs['settle_seconds'] = ui.number(
                'Settle (s)', 
                value=self.camera_data.get('settle_seconds', 5),
                min=1, max=30
            ).classes('w-full').props('outlined')
    
    def _render_presets(self):
        """Render presets section."""
        ui.label('PTZ Presets & Thermal Nodes').classes('text-subtitle1 font-bold mb-2')
        
        presets = self.camera_data.get('preset_thermals', [])
        if not presets:
            ui.label('No presets configured').classes('text-warning')
            with ui.row().classes('mt-2'):
                ui.button('Add First Preset', icon='add', color='green', 
                         on_click=lambda: self._add_preset_dialog())
        else:
            # Table header
            with ui.row().classes('w-full font-bold mb-2 bg-blue-grey-1 p-2 rounded'):
                ui.label('Preset').classes('w-32')
                ui.label('Nodes').classes('flex-grow')
                ui.label('Actions').classes('w-32')
            
            # Each preset as a row
            for preset_idx, preset in enumerate(presets):
                self._render_preset_row(preset, preset_idx)
            
            # Add preset button
            with ui.row().classes('w-full justify-center mt-2'):
                ui.button('Add Preset', icon='add', color='green', 
                         on_click=lambda: self._add_preset_dialog())
    
    def _render_preset_row(self, preset: Dict[str, Any], preset_idx: int):
        """Render a single preset row."""
        with ui.card().classes('w-full mb-2 p-3 hover:shadow-lg transition-shadow'):
            with ui.row().classes('w-full items-center gap-4'):
                # Preset name
                with ui.column().classes('w-32'):
                    ui.label(f"🎯 {preset.get('preset_name', f'Preset {preset_idx+1}')}") \
                        .classes('font-bold text-primary')
                    ui.label(f"ID: {preset_idx + 1}").classes('text-xs text-grey')
                
                # Nodes info
                with ui.column().classes('flex-grow'):
                    nodes = preset.get('nodes', [])
                    if nodes:
                        with ui.row().classes('flex-wrap gap-2'):
                            for node_idx, node in enumerate(nodes):
                                with ui.badge(f"{node.get('name_node', f'Node {node_idx+1}')}") \
                                    .props('color=teal'):
                                    ui.tooltip(
                                        f"SID: {node.get('SID', 'N/A')}\n"
                                        f"Area ID: {node.get('ID_node', 'N/A')}"
                                    )
                    else:
                        ui.label('No nodes').classes('text-grey italic')
                
                # Actions
                with ui.column().classes('w-32 gap-1'):
                    ui.button(
                        icon='edit', 
                        color='blue',
                        on_click=lambda idx=preset_idx: self._edit_preset_dialog(idx)
                    ).props('flat dense').tooltip('Edit Preset')
                    
                    ui.button(
                        icon='delete', 
                        color='red',
                        on_click=lambda idx=preset_idx: self._delete_preset(idx)
                    ).props('flat dense').tooltip('Delete Preset')
    
    def _render_urls(self):
        """Render additional settings section."""
        ui.label('Additional Settings').classes('text-subtitle1 font-bold mb-2')
        with ui.column().classes('w-full gap-2'):
            self.inputs['img_server_host'] = ui.input(
                'Image Server Host', 
                value=self.camera_data.get('img_server_host', ''),
                placeholder='e.g., 192.168.1.163'
            ).classes('w-full').props('outlined dense')
            
            ui.label('💡 URLs are auto-generated from url_templates', ) \
                .classes('text-caption text-grey-7 mt-2')
    
    def _render_actions(self):
        """Render action buttons."""
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', icon='close', color='grey', 
                     on_click=self._cancel_changes).props('outline')
            ui.button('Save Changes', icon='save', color='primary', 
                     on_click=self._save_changes)
    
    def _collect_data(self) -> Dict[str, Any]:
        """Collect data from all inputs."""
        data = {
            'camera_name': self.inputs['camera_name'].value,
            'camera_ip': self.inputs['camera_ip'].value,
            'username': self.inputs['username'].value,
            'password': self.inputs['password'].value,
            'interval_seconds': int(self.inputs['interval_seconds'].value),
            'timeout_seconds': int(self.inputs['timeout_seconds'].value),
            'settle_seconds': int(self.inputs['settle_seconds'].value),
            'img_server_host': self.inputs['img_server_host'].value,
            'preset_thermals': self.camera_data.get('preset_thermals', []),
            'url_templates': self.camera_data.get('url_templates', {})
        }
        return data
    
    def _save_changes(self):
        """Save camera configuration."""
        try:
            # Collect data
            updated_data = self._collect_data()
            
            # Validate
            if not updated_data['camera_name']:
                ui.notify('❌ Camera name is required', type='negative')
                return
            
            if not updated_data['camera_ip']:
                ui.notify('❌ Camera IP is required', type='negative')
                return
            
            # Save to config
            if save_config_file(self.cam_idx, updated_data):
                ui.notify('✅ Configuration saved successfully!', type='positive')
                if self.on_save_callback:
                    self.on_save_callback()
            else:
                ui.notify('❌ Failed to save configuration', type='negative')
        
        except Exception as e:
            ui.notify(f'❌ Error: {str(e)}', type='negative')
    
    def _cancel_changes(self):
        """Cancel changes and reload."""
        ui.notify('Cancelled', type='info')
        # Reload page to reset
        ui.navigate.reload()
    
    def _edit_preset_dialog(self, preset_idx: int):
        """Open dialog to edit preset."""
        preset = self.camera_data['preset_thermals'][preset_idx]
        
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-2xl'):
            ui.label(f'Edit Preset: {preset.get("preset_name", "")}').classes('text-h6 mb-4')
            
            # Preset name
            preset_name_input = ui.input('Preset Name', value=preset.get('preset_name', '')) \
                .classes('w-full mb-2').props('outlined')
            
            # Preset ID
            preset_id_input = ui.number('Preset ID', value=preset.get('preset_id', 1), min=1, max=99) \
                .classes('w-full mb-4').props('outlined')
            ui.label('💡 URL will be auto-generated: ...presetID=${preset_id}') \
                .classes('text-caption text-grey-7 mb-4')
            
            # Nodes
            ui.label('Thermal Nodes:').classes('text-subtitle2 font-bold mb-2')
            nodes = preset.get('nodes', [])
            
            node_inputs = []
            for node_idx, node in enumerate(nodes):
                with ui.expansion(f"Node {node_idx + 1}: {node.get('name_node', '')}") \
                    .classes('w-full mb-2'):
                    with ui.column().classes('w-full gap-2 p-2'):
                        node_data = {
                            'name': ui.input('Node Name', value=node.get('name_node', '')) \
                                .classes('w-full').props('outlined dense'),
                            'sid': ui.input('SID', value=node.get('SID', '')) \
                                .classes('w-full').props('outlined dense'),
                            'node_id': ui.number('Node ID', value=node.get('ID_node', 0), min=0) \
                                .classes('w-full').props('outlined dense'),
                            'area_id': ui.number('Area ID', value=node.get('area_id', 0), min=0, max=99) \
                                .classes('w-full').props('outlined dense'),
                        }
                        node_inputs.append(node_data)
                        ui.label('💡 URL: ...areaID=${area_id}').classes('text-caption text-grey-7')
            
            ui.separator().classes('my-4')
            
            # Actions
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Save', color='primary', on_click=lambda: self._save_preset_edit(
                    preset_idx, preset_name_input, preset_id_input, node_inputs, dialog
                ))
        
        dialog.open()
    
    def _save_preset_edit(self, preset_idx, preset_name_input, preset_id_input, node_inputs, dialog):
        """Save preset edit."""
        # Update preset data
        preset = self.camera_data['preset_thermals'][preset_idx]
        preset['preset_name'] = preset_name_input.value
        preset['preset_id'] = int(preset_id_input.value)
        
        # Update nodes
        for idx, node_data in enumerate(node_inputs):
            if idx < len(preset['nodes']):
                preset['nodes'][idx].update({
                    'name_node': node_data['name'].value,
                    'SID': node_data['sid'].value,
                    'ID_node': int(node_data['node_id'].value),
                    'area_id': int(node_data['area_id'].value)
                })
        
        dialog.close()
        ui.notify('✅ Preset updated', type='positive')
        ui.navigate.reload()
    
    def _add_preset_dialog(self):
        """Open dialog to add new preset."""
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-2xl'):
            ui.label('Add New Preset').classes('text-h6 mb-4')
            
            preset_name = ui.input('Preset Name', placeholder='e.g., KV4') \
                .classes('w-full mb-2').props('outlined')
            preset_id = ui.number('Preset ID', value=1, min=1, max=99) \
                .classes('w-full mb-2').props('outlined')
            ui.label('💡 URL will be auto-generated from url_templates').classes('text-caption text-grey-7 mb-4')
            
            ui.separator().classes('my-4')
            
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Add', color='primary', on_click=lambda: self._save_new_preset(
                    preset_name.value, int(preset_id.value), dialog
                ))
        
        dialog.open()
    
    def _save_new_preset(self, name: str, preset_id: int, dialog):
        """Save new preset."""
        if not name:
            ui.notify('❌ Preset name is required', type='negative')
            return
        
        new_preset = {
            'preset_name': name,
            'preset_id': preset_id,
            'nodes': []
        }
        
        if 'preset_thermals' not in self.camera_data:
            self.camera_data['preset_thermals'] = []
        
        self.camera_data['preset_thermals'].append(new_preset)
        dialog.close()
        ui.notify('✅ Preset added', type='positive')
        ui.navigate.reload()
    
    def _delete_preset(self, preset_idx: int):
        """Delete preset with confirmation."""
        preset_name = self.camera_data['preset_thermals'][preset_idx].get('preset_name', f'Preset {preset_idx+1}')
        
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Delete Preset: {preset_name}?').classes('text-h6 mb-4')
            ui.label('This action cannot be undone.').classes('text-warning mb-4')
            
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Delete', color='red', on_click=lambda: self._confirm_delete_preset(
                    preset_idx, dialog
                ))
        
        dialog.open()
    
    def _confirm_delete_preset(self, preset_idx: int, dialog):
        """Confirm and delete preset."""
        del self.camera_data['preset_thermals'][preset_idx]
        dialog.close()
        ui.notify('✅ Preset deleted', type='positive')
        ui.navigate.reload()


def save_config_file(cam_idx: int, camera_data: Dict[str, Any]) -> bool:
    """
    Save camera configuration to config.json file.
    
    Args:
        cam_idx: Camera index
        camera_data: Updated camera data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load current config
        with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Update camera data
        if cam_idx < len(config['cameras']):
            config['cameras'][cam_idx] = camera_data
        else:
            return False
        
        # Save to file
        with open(DEFAULT_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return True
    
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def show_settings_tab():
    """Show settings tab with camera configuration editor."""
    ui.label('Camera Configuration').classes('text-h5 font-bold mb-4')
    
    # Refresh button
    with ui.row().classes('w-full justify-end mb-4'):
        ui.button('Refresh', icon='refresh', on_click=lambda: ui.navigate.reload()) \
            .props('outline')
    
    # Load current config
    config = load_config()
    cameras = config.get("cameras", [])
    
    if not cameras:
        ui.label('No cameras configured').classes('text-warning')
        with ui.row().classes('mt-4'):
            ui.button('Add First Camera', icon='add_circle', color='green', 
                     on_click=add_new_camera)
        return
    
    # Render each camera editor
    for cam_idx, camera in enumerate(cameras):
        editor = CameraEditor(camera, cam_idx, on_save_callback=lambda: ui.navigate.reload())
        editor.render()
    
    # Add new camera button
    with ui.row().classes('w-full justify-center mt-4'):
        ui.button('Add New Camera', icon='add_circle', color='green', 
                 on_click=add_new_camera).props('size=lg')


def add_new_camera():
    """Add a new camera to configuration."""
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-xl'):
        ui.label('Add New Camera').classes('text-h6 mb-4')
        
        camera_name = ui.input('Camera Name', placeholder='e.g., 000100010009') \
            .classes('w-full mb-2').props('outlined')
        camera_ip = ui.input('Camera IP', placeholder='e.g., 192.168.1.172') \
            .classes('w-full mb-2').props('outlined')
        username = ui.input('Username', placeholder='admin') \
            .classes('w-full mb-2').props('outlined')
        password = ui.input('Password', password=True, password_toggle_button=True) \
            .classes('w-full mb-4').props('outlined')
        
        ui.separator().classes('my-4')
        
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Cancel', on_click=dialog.close).props('flat')
            ui.button('Add', color='primary', on_click=lambda: _save_new_camera(
                camera_name.value, camera_ip.value, username.value, password.value, dialog
            ))
    
    dialog.open()


def _save_new_camera(name: str, ip: str, username: str, password: str, dialog):
    """Save new camera to config."""
    if not name or not ip:
        ui.notify('❌ Camera name and IP are required', type='negative')
        return
    
    try:
        # Load current config
        with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Create new camera
        new_camera = {
            'camera_name': name,
            'camera_ip': ip,
            'username': username,
            'password': password,
            'interval_seconds': 30,
            'timeout_seconds': 5,
            'settle_seconds': 5,
            'preset_thermals': [],
            'img_server_host': '192.168.1.163',
            'url_templates': {
                'preset': 'http://${camera_ip}/cgi-bin/ptz.cgi?cameraID=1&action=presetInvoke&presetID=${preset_id}',
                'area_temperature': 'http://${camera_ip}/cgi-bin/param.cgi?action=get&type=areaTemperature&cameraID=1&areaID=${area_id}',
                'rtsp': 'http://${camera_ip}/cgi-bin/video.cgi?type=RTSP&cameraID=1&streamID=1',
                'snapshot': 'http://${camera_ip}/cgi-bin/image.cgi?cameraID=1&quality=5',
                'ptz_base': 'http://${camera_ip}/cgi-bin/ptz.cgi?cameraID=1'
            }
        }
        
        config['cameras'].append(new_camera)
        
        # Save to file
        with open(DEFAULT_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        dialog.close()
        ui.notify('✅ Camera added successfully!', type='positive')
        ui.navigate.reload()
    
    except Exception as e:
        ui.notify(f'❌ Error: {str(e)}', type='negative')


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
                app.storage.user.pop('logged_in', None)
                ui.navigate.to('/login')

            ui.button('Logout', on_click=do_logout,
                      color='red').classes('ml-auto')

        with ui.tab_panel('s'):
            show_settings_tab()

        with ui.tab_panel('a'):
            ui.label('SES 110kV Thermal Camera Monitor').classes('text-h5 font-bold mb-2')
            ui.label('Version 1.0.0').classes('mb-4')
            ui.separator().classes('my-4')
            ui.label('Features:').classes('font-bold')
            ui.label('• Multi-camera thermal monitoring')
            ui.label('• PTZ control with Auto/Manual modes')
            ui.label('• MQTT integration')
            ui.label('• Real-time temperature display')

    # Update data
    def update_ui():
        try:
            data = out_queue.get_nowait()
            if data.get('type') == 'temperature':
                text = f'{data["node_thermal"]}: {data.get("temperature", {}).get("value", "N/A")} °C at {data["timestamp"]}'
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
            ui.navigate.to('/login')
        else:
            show_main_ui(out_queue)

    @ui.page('/login')
    def login_page():
        login_screen()
