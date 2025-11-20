from nicegui import ui, app
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from config_loader import load_config, DEFAULT_CONFIG_PATH


USERNAME = "admin"
PASSWORD = "1234"


def notify_custom(message: str, type: str = 'positive'):
    """
    Custom notification with better styling.
    
    Args:
        message: Message to display
        type: 'positive', 'negative', 'warning', or 'info'
    """
    ui.notify(
        message,
        position='top-right',
        type=type,
        close_button=True,
        timeout=5000,
    )


class CameraEditor:
    """Camera configuration editor with data binding."""
    
    def __init__(self, camera_data: Dict[str, Any], cam_idx: int, on_save_callback=None):
        self.camera_data = camera_data
        self.cam_idx = cam_idx
        self.on_save_callback = on_save_callback
        
        # Input references for data binding
        self.inputs = {}
    
    def _reload_camera_data(self):
        """Reload camera data from config file."""
        from config_loader import load_config
        config = load_config()
        cameras = config.get("cameras", [])
        if self.cam_idx < len(cameras):
            self.camera_data = cameras[self.cam_idx]
    
    def render(self):
        """Render camera editor UI."""
        # Get saved expansion and tab state
        storage_key = f'camera_{self.cam_idx}'
        is_expanded = app.storage.user.get(f'{storage_key}_expanded', False)
        active_camera_tab = app.storage.user.get(f'{storage_key}_tab', 'basic')
        
        with ui.expansion(
            f"📹 {self.camera_data.get('camera_sid', f'Camera {self.cam_idx+1}')}", 
            icon='videocam',
            value=is_expanded
        ).classes('w-full mb-4') as expansion:
            # Save expansion state when toggled
            expansion.on_value_change(
                lambda e, key=storage_key: app.storage.user.update({f'{key}_expanded': e.value})
            )
            
            with ui.card().classes('w-full'):
                # Create tabs
                with ui.tabs().classes('w-full') as tabs:
                    basic_tab = ui.tab('basic', label='Basic', icon='info')
                    preset_tab = ui.tab('preset', label='Presets', icon='dashboard')
                    additional_tab = ui.tab('additional', label='Additional', icon='settings')
                
                # Save camera tab state when changed
                tabs.on_value_change(
                    lambda e, key=storage_key: app.storage.user.update({f'{key}_tab': e.value})
                )
                
                # Create tab panels
                with ui.tab_panels(tabs, value=active_camera_tab).classes('w-full'):
                    with ui.tab_panel('basic'):
                        self._render_basic_info()
                        
                    with ui.tab_panel('preset'):
                        self._render_presets()
                        
                    with ui.tab_panel('additional'):
                        self._render_urls()
                
                # Actions at the bottom (outside tabs)
                ui.separator().classes('my-4')
                self._render_actions()
    
    def _render_basic_info(self):
        """Render basic camera information section."""
        ui.label('Camera Configuration').classes('text-subtitle2 text-grey-7 mb-3')
        
        with ui.grid(columns=2).classes('w-full gap-4 mb-4'):
            self.inputs['camera_sid'] = ui.input(
                'Camera SID', 
                value=self.camera_data.get('camera_sid', '')
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
    
    @ui.refreshable
    def _render_presets(self):
        """Render presets section."""
        presets = self.camera_data.get('preset_thermals', [])
        
        # Summary header
        with ui.row().classes('w-full items-center justify-between mb-3'):
            ui.label('PTZ Presets & Thermal Nodes').classes('text-subtitle2 text-grey-7')
            with ui.badge(str(len(presets)), color='primary'):
                ui.tooltip(f'{len(presets)} preset(s) configured')
        
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
        ui.label('Additional Settings & URL Templates').classes('text-subtitle2 text-grey-7 mb-3')
        
        with ui.column().classes('w-full gap-4'):
            # Image Server
            ui.label('📷 Image Server').classes('text-subtitle2 font-bold')
            self.inputs['img_server_host'] = ui.input(
                'Image Server Host', 
                value=self.camera_data.get('img_server_host', ''),
                placeholder='e.g., 192.168.1.163'
            ).classes('w-full').props('outlined')
            ui.label('Server to store snapshot images').classes('text-caption text-grey-7')
            
            ui.separator()
            
            # URL Templates Info
            ui.label('🔗 URL Templates').classes('text-subtitle2 font-bold')
            ui.label('💡 All camera URLs are auto-generated from these templates:').classes('text-caption text-grey-7 mb-2')
            
            url_templates = self.camera_data.get('url_templates', {})
            if url_templates:
                with ui.expansion('View URL Templates', icon='visibility').classes('w-full'):
                    for key, template in url_templates.items():
                        with ui.row().classes('w-full items-center gap-2 mb-2'):
                            ui.label(f'{key}:').classes('text-weight-bold min-w-32')
                            ui.label(template).classes('text-grey-7 text-xs break-all')
            else:
                ui.label('⚠️ No URL templates configured').classes('text-warning')
    
    def _render_actions(self):
        """Render action buttons."""
        with ui.row().classes('w-full justify-between gap-2'):
            # Delete button on the left
            ui.button('Delete Camera', icon='delete', color='red', 
                     on_click=self._delete_camera).props('outline')
            
            # Save/Cancel buttons on the right
            with ui.row().classes('gap-2'):
                ui.button('Cancel', icon='close', color='grey', 
                         on_click=self._cancel_changes).props('outline')
                ui.button('Save Changes', icon='save', color='primary', 
                         on_click=self._save_changes)
    
    def _collect_data(self) -> Dict[str, Any]:
        """Collect data from all inputs."""
        data = {
            'camera_sid': self.inputs['camera_sid'].value,
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
            if not updated_data['camera_sid']:
                notify_custom('❌ Camera SID is required', type='negative')
                return
            
            if not updated_data['camera_ip']:
                notify_custom('❌ Camera IP is required', type='negative')
                return
            
            # Save to config
            if save_config_file(self.cam_idx, updated_data):
                notify_custom('✅ Configuration saved! Reloading...', type='positive')
                # Delay reload to show notification
                if self.on_save_callback:
                    ui.timer(1.0, self.on_save_callback, once=True)
            else:
                notify_custom('❌ Failed to save configuration', type='negative')
        
        except Exception as e:
            notify_custom(f'❌ Error: {str(e)}', type='negative')
    
    def _cancel_changes(self):
        """Cancel changes and reload."""
        notify_custom('ℹ️ Changes cancelled. Reloading...', type='info')
        # Delay reload to show notification
        ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
    
    def _delete_camera(self):
        """Delete camera with confirmation dialog."""
        camera_sid = self.camera_data.get('camera_sid', f'Camera {self.cam_idx+1}')
        
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Delete Camera: {camera_sid}?').classes('text-h6 mb-4')
            ui.label('⚠️ This will permanently delete this camera and all its presets.').classes('text-warning mb-4')
            ui.label('This action cannot be undone.').classes('text-grey mb-4')
            
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Delete', color='red', on_click=lambda: self._confirm_delete_camera(dialog))
        
        dialog.open()
    
    def _confirm_delete_camera(self, dialog):
        """Confirm and delete camera."""
        try:
            # Load current config
            with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Remove camera at index
            if self.cam_idx < len(config['cameras']):
                camera_sid = config['cameras'][self.cam_idx].get('camera_sid', f'Camera {self.cam_idx+1}')
                del config['cameras'][self.cam_idx]
                
                # Save to file
                with open(DEFAULT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                dialog.close()
                notify_custom(f'🗑️ Camera "{camera_sid}" deleted! Reloading...', type='warning')
                # Delay reload to show notification
                ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
            else:
                notify_custom('❌ Camera not found', type='negative')
        
        except Exception as e:
            notify_custom(f'❌ Error deleting camera: {str(e)}', type='negative')
    
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
            
            # Nodes section header with Add button
            with ui.row().classes('w-full justify-between items-center mb-2'):
                ui.label('Thermal Nodes:').classes('text-subtitle2 font-bold')
                ui.button('Add Node', icon='add', color='green', 
                         on_click=lambda: self._add_node_to_dialog(nodes_container, node_inputs)) \
                    .props('dense outline')
            
            # Nodes container
            nodes_container = ui.column().classes('w-full gap-2')
            
            nodes = preset.get('nodes', [])
            node_inputs = []
            
            with nodes_container:
                for node_idx, node in enumerate(nodes):
                    self._create_node_card(node_inputs, node_idx, node, nodes_container)
            
            ui.separator().classes('my-4')
            
            # Actions
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Save & Continue', color='primary', icon='save', 
                         on_click=lambda: self._save_preset_edit(
                    preset_idx, preset_name_input, preset_id_input, node_inputs, dialog, reopen=True
                ))
                ui.button('Save & Close', color='green', icon='check',
                         on_click=lambda: self._save_preset_edit(
                    preset_idx, preset_name_input, preset_id_input, node_inputs, dialog, reopen=False
                )).props('outline')
        
        dialog.open()
    
    def _create_node_card(self, node_inputs, node_idx, node, container):
        """Create a node input card with delete button."""
        with ui.expansion(f"Node {node_idx + 1}: {node.get('name_node', 'New Node')}") \
            .classes('w-full') as expansion:
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
                    'expansion': expansion
                }
                ui.label('💡 URL: ...areaID=${area_id}').classes('text-caption text-grey-7')
                
                # Delete button
                ui.button('Delete Node', icon='delete', color='red',
                         on_click=lambda n=node_data: self._remove_node_from_dialog(n, node_inputs)) \
                    .props('dense flat').classes('mt-2')
                
                node_inputs.append(node_data)
    
    def _add_node_to_dialog(self, container, node_inputs):
        """Add a new node to the edit dialog."""
        node_idx = len(node_inputs)
        new_node = {
            'name_node': f'New Node {node_idx + 1}',
            'SID': '',
            'ID_node': node_idx,
            'area_id': node_idx
        }
        
        with container:
            self._create_node_card(node_inputs, node_idx, new_node, container)
        
        notify_custom(f'➕ Node {node_idx + 1} added', type='info')
    
    def _remove_node_from_dialog(self, node_data, node_inputs):
        """Remove a node from the edit dialog."""
        # Remove from list
        node_inputs.remove(node_data)
        
        # Remove UI element
        node_data['expansion'].delete()
        
        notify_custom('🗑️ Node removed', type='info')
    
    def _save_preset_edit(self, preset_idx, preset_name_input, preset_id_input, node_inputs, dialog, reopen=False):
        """Save preset edit."""
        # Update preset data
        preset = self.camera_data['preset_thermals'][preset_idx]
        preset['preset_name'] = preset_name_input.value
        preset['preset_id'] = int(preset_id_input.value)
        
        # Rebuild nodes list from inputs (handles add/delete)
        new_nodes = []
        for node_data in node_inputs:
            new_nodes.append({
                'name_node': node_data['name'].value,
                'SID': node_data['sid'].value,
                'ID_node': int(node_data['node_id'].value),
                'area_id': int(node_data['area_id'].value)
            })
        
        preset['nodes'] = new_nodes
        
        # Save to config file
        if save_config_file(self.cam_idx, self.camera_data):
            if reopen:
                # Save & Continue: just update and notify, keep dialog open
                notify_custom('✅ Preset saved! You can continue editing.', type='positive')
                # Reload camera data in background to sync
                self._reload_camera_data()
            else:
                # Save & Close: close dialog and refresh list
                notify_custom('✅ Preset updated!', type='positive')
                dialog.close()
                self._reload_camera_data()
                self._render_presets.refresh()
        else:
            notify_custom('❌ Failed to save preset', type='negative')
    
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
            notify_custom('❌ Preset name is required', type='negative')
            return
        
        new_preset = {
            'preset_name': name,
            'preset_id': preset_id,
            'nodes': []
        }
        
        if 'preset_thermals' not in self.camera_data:
            self.camera_data['preset_thermals'] = []
        
        self.camera_data['preset_thermals'].append(new_preset)
        
        # Save to config file
        if save_config_file(self.cam_idx, self.camera_data):
            dialog.close()
            notify_custom('✅ Preset added!', type='positive')
            # Reload camera data and refresh preset UI
            self._reload_camera_data()
            self._render_presets.refresh()
            # Open edit dialog for the newly added preset
            new_preset_idx = len(self.camera_data['preset_thermals']) - 1
            ui.timer(0.3, lambda: self._edit_preset_dialog(new_preset_idx), once=True)
        else:
            notify_custom('❌ Failed to save preset', type='negative')
    
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
        
        # Save to config file
        if save_config_file(self.cam_idx, self.camera_data):
            dialog.close()
            notify_custom('⚠️ Preset deleted!', type='warning')
            # Reload camera data and refresh preset UI
            self._reload_camera_data()
            self._render_presets.refresh()
        else:
            notify_custom('❌ Failed to delete preset', type='negative')


def clean_auto_generated_urls(camera_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove auto-generated URLs from camera data before saving.
    These URLs will be regenerated from templates on load.
    """
    import copy
    cleaned_data = copy.deepcopy(camera_data)
    
    # Remove auto-generated camera-level URLs
    cleaned_data.pop('url_snapshot', None)
    cleaned_data.pop('url_ptz_base', None)
    cleaned_data.pop('url_get_rtsp_url', None)
    
    # Remove global settings (should be at global level, not camera level)
    cleaned_data.pop('url_templates', None)
    cleaned_data.pop('img_server_host', None)
    
    # Clean preset_thermals
    if 'preset_thermals' in cleaned_data:
        for preset in cleaned_data['preset_thermals']:
            # Remove auto-generated preset URL
            preset.pop('url_presetID', None)
            
            # Clean nodes
            if 'nodes' in preset:
                for node in preset['nodes']:
                    # Remove auto-generated node URL
                    node.pop('url_areaTemperature', None)
    
    return cleaned_data


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
        
        # Clean auto-generated URLs before saving
        cleaned_data = clean_auto_generated_urls(camera_data)
        
        # Update camera data
        if cam_idx < len(config['cameras']):
            config['cameras'][cam_idx] = cleaned_data
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
    
    # Buttons row
    with ui.row().classes('w-full justify-end mb-4'):
        # Refresh button
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
        
        camera_sid = ui.input('Camera SID', placeholder='e.g., 000100010009') \
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
                camera_sid.value, camera_ip.value, username.value, password.value, dialog
            ))
    
    dialog.open()


def _save_new_camera(name: str, ip: str, username: str, password: str, dialog):
    """Save new camera to config."""
    if not name or not ip:
        notify_custom('❌ Camera SID and IP are required', type='negative')
        return
    
    try:
        # Load current config
        with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Create new camera
        new_camera = {
            'camera_sid': name,
            'camera_ip': ip,
            'username': username,
            'password': password,
            'interval_seconds': 30,
            'timeout_seconds': 5,
            'settle_seconds': 5,
            'preset_thermals': []
        }
        
        config['cameras'].append(new_camera)
        
        # Save to file
        with open(DEFAULT_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        dialog.close()
        notify_custom('✅ Camera added! Reloading...', type='positive')
        # Delay reload to show notification
        ui.timer(1.0, lambda: ui.navigate.reload(), once=True)
    
    except Exception as e:
        notify_custom(f'❌ Error: {str(e)}', type='negative')


def show_main_ui(out_queue):
    # Restore last active tab from storage (default: 'h' for Home)
    active_tab = app.storage.user.get('active_tab', 'h')
    
    with ui.tabs() as tabs:
        ui.tab('h', label='Home', icon='home')
        ui.tab('s', label='Setup', icon='settings')
        ui.tab('a', label='About', icon='info')
    
    # Save active tab to storage when changed
    tabs.on_value_change(lambda e: app.storage.user.update({'active_tab': e.value}))

    with ui.tab_panels(tabs, value=active_tab).classes('w-full'):
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
                notify_custom('❌ Wrong credentials', type='negative')

        ui.button('Login', on_click=attempt_login).classes('mt-2')


def register_pages(out_queue):
    # Add custom CSS for better toast notifications
    ui.add_head_html('''
        <style>
            /* Beautiful toast notification styling */
            .q-notification {
                z-index: 99999 !important;
                min-width: 350px !important;
                font-size: 16px !important;
                font-weight: 600 !important;
                padding: 20px 24px !important;
                border-radius: 12px !important;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4) !important;
                animation: slideInRight 0.3s ease-out !important;
            }
            
            /* Success - Green gradient */
            .q-notification--positive {
                background: linear-gradient(135deg, #4CAF50, #45a049) !important;
                color: white !important;
                border-left: 5px solid #2E7D32 !important;
            }
            
            /* Error - Red gradient */
            .q-notification--negative {
                background: linear-gradient(135deg, #F44336, #e53935) !important;
                color: white !important;
                border-left: 5px solid #C62828 !important;
            }
            
            /* Warning - Orange gradient */
            .q-notification--warning {
                background: linear-gradient(135deg, #FF9800, #fb8c00) !important;
                color: white !important;
                border-left: 5px solid #E65100 !important;
            }
            
            /* Info - Blue gradient */
            .q-notification--info {
                background: linear-gradient(135deg, #2196F3, #1e88e5) !important;
                color: white !important;
                border-left: 5px solid #1565C0 !important;
            }
            
            /* Slide in from right animation */
            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            
            /* Position */
            .q-notifications__list--top-right {
                top: 20px !important;
                right: 20px !important;
                z-index: 99999 !important;
            }
            
            /* Message text */
            .q-notification__message {
                color: white !important;
                font-weight: 600 !important;
                line-height: 1.5 !important;
            }
            
            /* Close button */
            .q-notification__actions .q-btn {
                color: rgba(255, 255, 255, 0.95) !important;
            }
            
            .q-notification__actions .q-btn:hover {
                background: rgba(255, 255, 255, 0.2) !important;
                border-radius: 50% !important;
            }
        </style>
    ''')
    
    @ui.page('/')
    def main_page():
        if not app.storage.user.get('logged_in'):
            ui.navigate.to('/login')
        else:
            show_main_ui(out_queue)

    @ui.page('/login')
    def login_page():
        login_screen()
