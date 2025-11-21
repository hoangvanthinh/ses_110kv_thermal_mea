from nicegui import ui, app
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from config_loader import load_config, DEFAULT_CONFIG_PATH


USERNAME = "admin"
PASSWORD = "1234"

# Global state for ping status: {camera_sid: is_online}
PING_STATUS: Dict[str, bool] = {}

# Global state for latest temperature readings: {camera_sid: {node: data}}
LATEST_TEMPS: Dict[str, Dict[str, Any]] = {}

# Global state for recent events (limited to last 50)
RECENT_EVENTS: List[Dict[str, Any]] = []


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
        
        camera_sid = self.camera_data.get('camera_sid')
        
        def get_title():
            name = self.camera_data.get('camera_name', 
                                       self.camera_data.get('camera_sid', f'Camera {self.cam_idx+1}'))
            
            # Get ping status
            is_online = PING_STATUS.get(camera_sid)
            indicator = "⚪" # Unknown/Pending
            if is_online is True:
                indicator = "🟢"
            elif is_online is False:
                indicator = "🔴"
                
            return f"{indicator} {name}"
        
        expansion = ui.expansion(
            get_title(), 
            icon='videocam',
            value=is_expanded
        ).classes('w-full mb-3 bg-white shadow-md rounded-lg border-l-4 border-orange-400 hover:shadow-lg transition-shadow')
        
        # Update title periodically to reflect ping status
        def update_header():
            new_title = get_title()
            if expansion._props.get('label') != new_title:
                expansion._props['label'] = new_title
                expansion.update()
            
        ui.timer(1.0, update_header)
        
        with expansion:
            # Save expansion state when toggled
            expansion.on_value_change(
                lambda e, key=storage_key: app.storage.user.update({f'{key}_expanded': e.value})
            )
            
            with ui.card().classes('w-full shadow-none'):
                # Create tabs - modern, clean design
                with ui.tabs().props('dense inline-label').classes('text-sm') as tabs:
                    basic_tab = ui.tab('basic', label='Basic', icon='info')
                    preset_tab = ui.tab('preset', label='Presets', icon='dashboard')
                    additional_tab = ui.tab('additional', label='Additional', icon='settings')
                
                # Save camera tab state when changed
                tabs.on_value_change(
                    lambda e, key=storage_key: app.storage.user.update({f'{key}_tab': e.value})
                )
                
                # Create tab panels
                with ui.tab_panels(tabs, value=active_camera_tab).classes('w-full pt-4'):
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
        """Render basic camera information section with modern UX."""
        # Section header
        with ui.row().classes('w-full items-center mb-4'):
            ui.icon('badge', size='sm').classes('text-sky-600')
            ui.label('Camera Information').classes('text-lg font-semibold text-sky-700 ml-2')
        
        # Identity section
        with ui.card().classes('w-full mb-4 p-4 bg-gradient-to-br from-sky-50 to-white'):
            ui.label('Identity').classes('text-sm font-bold text-sky-700 mb-3')
            with ui.grid(columns=2).classes('w-full gap-4'):
                with ui.column().classes('w-full'):
                    self.inputs['camera_name'] = ui.input(
                        'Camera Name',
                        value=self.camera_data.get('camera_name', ''),
                        placeholder='e.g., Camera Ba Son 1'
                    ).classes('w-full').props('outlined dense')
                    ui.label('Display name for this camera').classes('text-xs text-grey-600 mt-1')
                
                with ui.column().classes('w-full'):
                    self.inputs['camera_sid'] = ui.input(
                        'Camera SID',
                        value=self.camera_data.get('camera_sid', ''),
                        placeholder='e.g., 000100010008'
                    ).classes('w-full').props('outlined dense')
                    ui.label('Unique identifier for the camera').classes('text-xs text-grey-600 mt-1')
        
        # Connection section
        with ui.card().classes('w-full mb-4 p-4 bg-gradient-to-br from-orange-50 to-white'):
            ui.label('Connection').classes('text-sm font-bold text-orange-700 mb-3')
            with ui.grid(columns=2).classes('w-full gap-4'):
                with ui.column().classes('w-full'):
                    self.inputs['camera_ip'] = ui.input(
                        'Camera IP',
                        value=self.camera_data.get('camera_ip', ''),
                        placeholder='e.g., 192.168.1.171'
                    ).classes('w-full').props('outlined dense')
                    ui.label('IP address of the camera').classes('text-xs text-grey-600 mt-1')
                
                with ui.column().classes('w-full'):
                    self.inputs['username'] = ui.input(
                        'Username',
                        value=self.camera_data.get('username', ''),
                        placeholder='admin'
                    ).classes('w-full').props('outlined dense')
                    ui.label('Authentication username').classes('text-xs text-grey-600 mt-1')
            
            with ui.column().classes('w-full mt-2'):
                self.inputs['password'] = ui.input(
                    'Password',
                    value=self.camera_data.get('password', ''),
                    password=True,
                    password_toggle_button=True,
                    placeholder='••••••••'
                ).classes('w-full').props('outlined dense')
                ui.label('Authentication password').classes('text-xs text-grey-600 mt-1')
        
        # Timing configuration section
        with ui.card().classes('w-full p-4 bg-gradient-to-br from-sky-50 to-white'):
            ui.label('Timing Configuration').classes('text-sm font-bold text-sky-700 mb-3')
            with ui.grid(columns=3).classes('w-full gap-4'):
                with ui.column().classes('w-full'):
                    self.inputs['interval_seconds'] = ui.number(
                        'Interval (s)',
                        value=self.camera_data.get('interval_seconds', 30),
                        min=1, max=300
                    ).classes('w-full').props('outlined dense')
                    ui.label('Polling interval').classes('text-xs text-grey-600 mt-1')
                
                with ui.column().classes('w-full'):
                    self.inputs['timeout_seconds'] = ui.number(
                        'Timeout (s)',
                        value=self.camera_data.get('timeout_seconds', 5),
                        min=1, max=30
                    ).classes('w-full').props('outlined dense')
                    ui.label('Request timeout').classes('text-xs text-grey-600 mt-1')
                
                with ui.column().classes('w-full'):
                    self.inputs['settle_seconds'] = ui.number(
                        'Settle (s)',
                        value=self.camera_data.get('settle_seconds', 5),
                        min=1, max=30
                    ).classes('w-full').props('outlined dense')
                    ui.label('PTZ settle time').classes('text-xs text-grey-600 mt-1')
    
    @ui.refreshable
    def _render_presets(self):
        """Render presets section in modern tree structure."""
        presets = self.camera_data.get('preset_thermals', [])
        
        # Add preset button and count badge
        with ui.row().classes('w-full items-center justify-between mb-4'):
            ui.button(
                '➕ Add Preset', 
                icon='add_circle_outline', 
                color='orange',
                on_click=lambda: self._add_preset_dialog()
            ).props('outline dense')
            
            if presets:
                with ui.badge(str(len(presets)), color='sky'):
                    ui.tooltip(f'{len(presets)} preset(s) configured')
        
        if not presets:
            # Empty state
            with ui.card().classes('w-full p-8 text-center bg-gradient-to-br from-orange-50 to-white'):
                ui.icon('dashboard_customize', size='xl').classes('text-orange-300 mb-3')
                ui.label('No presets configured yet').classes('text-orange-600 font-medium mb-2')
                ui.label('Click "Add Preset" to create your first preset').classes('text-sm text-grey-600')
        else:
            # Tree structure with modern cards
            for preset_idx, preset in enumerate(presets):
                self._render_preset_tree_node(preset, preset_idx)
    
    def _render_preset_tree_node(self, preset: Dict[str, Any], preset_idx: int):
        """Render a preset as a modern tree node."""
        preset_name = preset.get('preset_name', f'Preset {preset_idx+1}')
        preset_id = preset.get('preset_id', preset_idx+1)
        nodes = preset.get('nodes', [])
        
        # Preset card with modern design
        with ui.card().classes('w-full mb-3 p-0 shadow-md hover:shadow-lg transition-all'):
            # Preset header
            with ui.row().classes('w-full items-center justify-between p-4 bg-gradient-to-r from-sky-100 via-white to-orange-50'):
                with ui.row().classes('items-center gap-3'):
                    ui.icon('dashboard', size='md').classes('text-sky-600')
                    with ui.column().classes('gap-0'):
                        ui.label(preset_name).classes('text-base font-bold text-sky-700')
                        ui.label(f'Preset ID: {preset_id} • {len(nodes)} node(s)').classes('text-xs text-grey-600')
                
                # Actions
                with ui.row().classes('gap-1'):
                    ui.button(icon='edit', color='sky',
                             on_click=lambda idx=preset_idx: self._edit_preset_dialog(idx)) \
                        .props('flat dense round').tooltip('Edit')
                    ui.button(icon='delete', color='red',
                             on_click=lambda idx=preset_idx: self._delete_preset(idx)) \
                        .props('flat dense round').tooltip('Delete')
            
            # Nodes section
            if nodes:
                with ui.column().classes('w-full p-4 pt-2 bg-white'):
                    ui.label(f'📍 Thermal Nodes ({len(nodes)})').classes('text-xs font-semibold text-grey-700 mb-2')
                    
                    with ui.grid(columns='repeat(auto-fill, minmax(250px, 1fr))').classes('w-full gap-3'):
                        for node_idx, node in enumerate(nodes):
                            self._render_node_compact_card(node, node_idx)
            else:
                with ui.row().classes('w-full p-4 justify-center bg-orange-50'):
                    ui.icon('info_outline', size='sm').classes('text-orange-400')
                    ui.label('No nodes configured').classes('text-sm text-orange-600 ml-2')
    
    def _render_node_compact_card(self, node: Dict[str, Any], node_idx: int):
        """Render a node as a compact card."""
        node_name = node.get('name_node', f'Node {node_idx+1}')
        node_sid = node.get('SID', 'N/A')
        area_id = node.get('area_id', 0)
        node_id = node.get('ID_node', 0)
        
        with ui.card().classes('w-full p-3 bg-gradient-to-br from-orange-50 to-white border-l-2 border-orange-400'):
            with ui.row().classes('w-full items-start justify-between mb-2'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('sensors', size='sm').classes('text-orange-600')
                    ui.label(node_name).classes('text-sm font-semibold text-orange-700')
            
            with ui.column().classes('w-full gap-1'):
                with ui.row().classes('items-center'):
                    ui.label('SID:').classes('text-xs font-medium text-grey-600 w-16')
                    ui.label(node_sid).classes('text-xs text-grey-800 font-mono')
                
                with ui.row().classes('items-center'):
                    ui.label('Node ID:').classes('text-xs font-medium text-grey-600 w-16')
                    ui.label(str(node_id)).classes('text-xs text-grey-800')
                
                with ui.row().classes('items-center'):
                    ui.label('Area ID:').classes('text-xs font-medium text-grey-600 w-16')
                    ui.label(str(area_id)).classes('text-xs text-grey-800')
    
    def _render_urls(self):
        """Render additional settings section with modern design."""
        # Image Server section
        with ui.card().classes('w-full mb-4 p-4 bg-gradient-to-br from-sky-50 to-white'):
            with ui.row().classes('w-full items-center mb-3'):
                ui.icon('cloud_upload', size='sm').classes('text-sky-600')
                ui.label('Image Server').classes('text-sm font-bold text-sky-700 ml-2')
            
            self.inputs['img_server_host'] = ui.input(
                'Server Host',
                value=self.camera_data.get('img_server_host', ''),
                placeholder='e.g., 192.168.1.163'
            ).classes('w-full').props('outlined dense')
            ui.label('Server to store snapshot images').classes('text-xs text-grey-600 mt-1')
        
        # URL Templates section
        with ui.card().classes('w-full p-4 bg-gradient-to-br from-orange-50 to-white'):
            with ui.row().classes('w-full items-center mb-3'):
                ui.icon('link', size='sm').classes('text-orange-600')
                ui.label('URL Templates').classes('text-sm font-bold text-orange-700 ml-2')
            
            ui.label('All camera URLs are auto-generated from these templates using ${camera_ip}, ${preset_id}, and ${area_id} variables.') \
                .classes('text-xs text-grey-600 mb-3')
            
            url_templates = self.camera_data.get('url_templates', {})
            if url_templates:
                with ui.expansion('View Templates', icon='code').classes('w-full bg-white'):
                    with ui.column().classes('w-full gap-2 p-2'):
                        for key, template in url_templates.items():
                            with ui.card().classes('w-full p-2 bg-grey-50'):
                                ui.label(key).classes('text-xs font-bold text-sky-700 mb-1')
                                ui.label(template).classes('text-xs text-grey-700 font-mono break-all')
            else:
                with ui.row().classes('items-center p-3 bg-orange-100 rounded'):
                    ui.icon('warning', size='sm').classes('text-orange-600')
                    ui.label('No URL templates configured').classes('text-sm text-orange-700 ml-2')
    
    def _render_actions(self):
        """Render action buttons with modern design."""
        with ui.card().classes('w-full p-4 bg-gradient-to-r from-grey-50 to-sky-50'):
            with ui.row().classes('w-full justify-between items-center'):
                # Delete button on the left - Danger zone
                with ui.row().classes('items-center gap-2'):
                    ui.icon('warning', size='sm').classes('text-red-600')
                    ui.button(
                        'Delete Camera', 
                        icon='delete_forever', 
                        color='red',
                        on_click=self._delete_camera
                    ).props('outline dense')
                
                # Primary actions on the right
                with ui.row().classes('gap-2'):
                    ui.button(
                        'Cancel', 
                        icon='close', 
                        color='grey',
                        on_click=self._cancel_changes
                    ).props('outline dense')
                    ui.button(
                        'Save Changes', 
                        icon='check_circle', 
                        color='sky',
                        on_click=self._save_changes
                    ).props('dense')
    
    def _collect_data(self) -> Dict[str, Any]:
        """Collect data from all inputs."""
        data = {
            'camera_name': self.inputs['camera_name'].value,
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
        camera_name = self.camera_data.get('camera_name', self.camera_data.get('camera_sid', f'Camera {self.cam_idx+1}'))
        
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Delete Camera: {camera_name}?').classes('text-h6 mb-4')
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
                camera_name = config['cameras'][self.cam_idx].get('camera_name', 
                    config['cameras'][self.cam_idx].get('camera_sid', f'Camera {self.cam_idx+1}'))
                del config['cameras'][self.cam_idx]
                
                # Save to file
                with open(DEFAULT_CONFIG_PATH, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                dialog.close()
                notify_custom(f'🗑️ Camera "{camera_name}" deleted! Reloading...', type='warning')
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
                ui.button('Add Node', icon='add', color='orange', 
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
                ui.button('Save & Continue', color='sky', icon='save', 
                         on_click=lambda: self._save_preset_edit(
                    preset_idx, preset_name_input, preset_id_input, node_inputs, dialog, reopen=True
                ))
                ui.button('Save & Close', color='orange', icon='check',
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
                ui.button('Add', color='orange', on_click=lambda: self._save_new_preset(
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
            ui.button('Add First Camera', icon='add_circle', color='orange', 
                     on_click=add_new_camera)
        return
    
    # Render each camera editor

    
    for cam_idx, camera in enumerate(cameras):
        editor = CameraEditor(camera, cam_idx, on_save_callback=lambda: ui.navigate.reload())
        editor.render()
    
    # Add new camera button
    with ui.row().classes('w-full justify-center mt-4'):
        ui.button('Add New Camera', icon='add_circle', color='orange', 
                 on_click=add_new_camera).props('size=lg')


def add_new_camera():
    """Add a new camera to configuration."""
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-xl'):
        ui.label('Add New Camera').classes('text-h6 mb-4')
        
        camera_name = ui.input('Camera Name', placeholder='e.g., Camera Ba Son 1') \
            .classes('w-full mb-2').props('outlined')
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
            ui.button('Add', color='orange', on_click=lambda: _save_new_camera(
                camera_name.value, camera_sid.value, camera_ip.value, username.value, password.value, dialog
            ))
    
    dialog.open()


def _save_new_camera(name: str, sid: str, ip: str, username: str, password: str, dialog):
    """Save new camera to config."""
    if not sid or not ip:
        notify_custom('❌ Camera SID and IP are required', type='negative')
        return
    
    try:
        # Load current config
        with open(DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Create new camera
        new_camera = {
            'camera_name': name or sid,  # Use SID as fallback if name is empty
            'camera_sid': sid,
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


def show_main_ui(out_queue, ui_queue):
    # Restore last active tab from storage (default: 'h' for Home)
    active_tab = app.storage.user.get('active_tab', 'h')
    
    def do_logout():
        app.storage.user.pop('logged_in', None)
        ui.navigate.to('/login')
    
    # Use splitter for vertical tabs layout
    with ui.splitter(value=15).classes('w-full h-screen') as splitter:
        with splitter.before:
            # Container for tabs and logout button
            with ui.column().classes('w-full h-full justify-between'):
                # Vertical tabs on top
                with ui.tabs().props('vertical').classes('w-full') as tabs:
                    ui.tab('h', label='Home', icon='home')
                    ui.tab('s', label='Setup', icon='settings')
                    ui.tab('a', label='About', icon='info')
                
                # Logout button at bottom
                ui.button('🚪 Logout', icon='logout', on_click=do_logout,
                          color='red').props('outline dense size=sm').classes('w-full')
        
        with splitter.after:
            # Tab panels on the right side
            with ui.tab_panels(tabs, value=active_tab).props('vertical').classes('w-full h-full'):
                with ui.tab_panel('h'):
                    # Dashboard Header
                    with ui.row().classes('w-full mb-4 gap-4'):
                        ui.label('📊 Dashboard').classes('text-3xl font-bold text-gray-800')
                    
                    # Overview Cards Row
                    with ui.row().classes('w-full gap-4 mb-4'):
                        # Total Cameras Card
                        with ui.card().classes('flex-1 bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg'):
                            ui.label('Total Cameras').classes('text-sm opacity-90 mb-1')
                            total_cameras_label = ui.label('0').classes('text-4xl font-bold')
                            ui.icon('videocam').classes('text-5xl opacity-20 absolute bottom-2 right-2')
                        
                        # Online Cameras Card
                        with ui.card().classes('flex-1 bg-gradient-to-br from-green-500 to-green-600 text-white shadow-lg'):
                            ui.label('Online').classes('text-sm opacity-90 mb-1')
                            online_cameras_label = ui.label('0').classes('text-4xl font-bold')
                            ui.icon('check_circle').classes('text-5xl opacity-20 absolute bottom-2 right-2')
                        
                        # Offline Cameras Card
                        with ui.card().classes('flex-1 bg-gradient-to-br from-red-500 to-red-600 text-white shadow-lg'):
                            ui.label('Offline').classes('text-sm opacity-90 mb-1')
                            offline_cameras_label = ui.label('0').classes('text-4xl font-bold')
                            ui.icon('cancel').classes('text-5xl opacity-20 absolute bottom-2 right-2')
                        
                        # MQTT Status Card
                        with ui.card().classes('flex-1 bg-gradient-to-br from-purple-500 to-purple-600 text-white shadow-lg'):
                            ui.label('MQTT Status').classes('text-sm opacity-90 mb-1')
                            mqtt_status_label = ui.label('Connected').classes('text-2xl font-bold')
                            ui.icon('cloud').classes('text-5xl opacity-20 absolute bottom-2 right-2')
                    
                    # Camera Status Grid
                    with ui.card().classes('w-full mb-4'):
                        ui.label('🎥 Camera Status').classes('text-xl font-bold mb-4 text-gray-800')
                        camera_status_container = ui.column().classes('w-full gap-2')
                    
                    # Recent Temperature Readings
                    with ui.card().classes('w-full mb-4'):
                        ui.label('🌡️ Recent Temperature Readings').classes('text-xl font-bold mb-4 text-gray-800')
                        temp_readings_container = ui.column().classes('w-full gap-2')
                    
                    # Recent Events
                    with ui.card().classes('w-full'):
                        with ui.row().classes('w-full items-center mb-4'):
                            ui.label('📋 Recent Events').classes('text-xl font-bold text-gray-800')
                            ui.space()
                            ui.button('Clear', icon='delete', on_click=lambda: RECENT_EVENTS.clear()).props('outline size=sm color=red')
                        events_container = ui.column().classes('w-full gap-1 max-h-64 overflow-y-auto')

                with ui.tab_panel('s'):
                    show_settings_tab()

                with ui.tab_panel('a'):
                    with ui.card().classes('w-full'):
                        ui.label('SES 110kV Thermal Camera Monitor').classes('text-h5 font-bold mb-2')
                        ui.label('Version 1.0.0').classes('mb-4')
                        ui.separator().classes('my-4')
                        ui.label('Features:').classes('font-bold')
                        ui.label('• Multi-camera thermal monitoring')
                        ui.label('• PTZ control with Auto/Manual modes')
                        ui.label('• MQTT integration')
                        ui.label('• Real-time temperature display')
    
    # Save active tab to storage when changed
    tabs.on_value_change(lambda e: app.storage.user.update({'active_tab': e.value}))

    # Update data
    def update_ui():
        try:
            # Process up to 10 messages at once to avoid backlog
            for _ in range(10):
                # First check UI queue for ping status
                if not ui_queue.empty():
                    data = ui_queue.get_nowait()
                    msg_type = data.get('type')
                    
                    if msg_type == 'ping_status':
                        camera_sid = data.get('camera_sid')
                        status = data.get('status')
                        print(f"UI received ping status: {camera_sid} -> {status}")  # Debug log
                        if camera_sid:
                            PING_STATUS[camera_sid] = (status == 'online')
                            # Add to recent events
                            event = {
                                'time': datetime.now().strftime('%H:%M:%S'),
                                'type': 'ping',
                                'message': f"Camera {camera_sid}: {status}",
                                'status': status
                            }
                            RECENT_EVENTS.insert(0, event)
                            if len(RECENT_EVENTS) > 50:
                                RECENT_EVENTS.pop()
                
                # Then check main queue for temperature data
                if not out_queue.empty():
                    data = out_queue.get_nowait()
                    msg_type = data.get('type')
                    
                    if msg_type == 'temperature':
                        camera_sid = data.get('camera')
                        node_thermal = data.get('node_thermal')
                        temp_data = data.get('temperature', {})
                        
                        # Update latest temps
                        if camera_sid not in LATEST_TEMPS:
                            LATEST_TEMPS[camera_sid] = {}
                        LATEST_TEMPS[camera_sid][node_thermal] = {
                            'value': temp_data.get('value', 'N/A'),
                            'timestamp': data.get('timestamp', ''),
                            'time': datetime.now().strftime('%H:%M:%S')
                        }
                        
                        # Add to recent events
                        event = {
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'type': 'temperature',
                            'message': f"{camera_sid}/{node_thermal}: {temp_data.get('value', 'N/A')} °C",
                            'status': 'normal'
                        }
                        RECENT_EVENTS.insert(0, event)
                        if len(RECENT_EVENTS) > 50:
                            RECENT_EVENTS.pop()
                        
        except Exception as e:
            print(f"Error in update_ui: {e}")
    
    # Update dashboard stats
    def update_dashboard():
        try:
            config = load_config()
            cameras = config.get('cameras', [])
            total = len(cameras)
            online = sum(1 for sid in [c.get('camera_sid') for c in cameras] if PING_STATUS.get(sid) == True)
            offline = sum(1 for sid in [c.get('camera_sid') for c in cameras] if PING_STATUS.get(sid) == False)
            
            total_cameras_label.text = str(total)
            online_cameras_label.text = str(online)
            offline_cameras_label.text = str(offline)
            
            # Update camera status grid
            camera_status_container.clear()
            for camera in cameras:
                sid = camera.get('camera_sid')
                name = camera.get('camera_name', sid)
                ip = camera.get('camera_ip', 'N/A')
                is_online = PING_STATUS.get(sid)
                
                with camera_status_container:
                    with ui.card().classes('w-full p-3 hover:shadow-lg transition-shadow'):
                        with ui.row().classes('w-full items-center gap-4'):
                            # Status indicator
                            if is_online is True:
                                ui.icon('check_circle').classes('text-3xl text-green-500')
                            elif is_online is False:
                                ui.icon('cancel').classes('text-3xl text-red-500')
                            else:
                                ui.icon('help').classes('text-3xl text-gray-400')
                            
                            # Camera info
                            with ui.column().classes('flex-1'):
                                ui.label(name).classes('font-bold text-lg')
                                ui.label(f'SID: {sid} | IP: {ip}').classes('text-sm text-gray-600')
                            
                            # Latest temp
                            with ui.column().classes('items-end'):
                                if sid in LATEST_TEMPS and LATEST_TEMPS[sid]:
                                    latest_node = list(LATEST_TEMPS[sid].keys())[-1]
                                    latest_temp = LATEST_TEMPS[sid][latest_node]
                                    ui.label(f"{latest_temp['value']} °C").classes('text-2xl font-bold text-orange-600')
                                    ui.label(f"{latest_node} @ {latest_temp['time']}").classes('text-xs text-gray-500')
                                else:
                                    ui.label('No data').classes('text-sm text-gray-400')
            
            # Update temperature readings
            temp_readings_container.clear()
            with temp_readings_container:
                if not LATEST_TEMPS:
                    ui.label('Waiting for temperature data...').classes('text-gray-500 italic')
                else:
                    for camera_sid, nodes in LATEST_TEMPS.items():
                        for node_name, temp_info in nodes.items():
                            with ui.card().classes('w-full p-2 bg-gray-50'):
                                with ui.row().classes('w-full items-center gap-3'):
                                    ui.icon('thermostat').classes('text-2xl text-orange-500')
                                    with ui.column().classes('flex-1'):
                                        ui.label(f"{camera_sid} / {node_name}").classes('font-semibold')
                                        ui.label(f"@ {temp_info['time']}").classes('text-xs text-gray-500')
                                    ui.label(f"{temp_info['value']} °C").classes('text-xl font-bold text-orange-600')
            
            # Update events
            events_container.clear()
            with events_container:
                if not RECENT_EVENTS:
                    ui.label('No events yet...').classes('text-gray-500 italic')
                else:
                    for event in RECENT_EVENTS[:20]:  # Show last 20
                        icon = 'wifi' if event['type'] == 'ping' else 'thermostat'
                        color = 'text-green-600' if event.get('status') == 'online' else 'text-red-600' if event.get('status') == 'offline' else 'text-blue-600'
                        
                        with ui.row().classes('w-full items-center gap-2 py-1 border-b border-gray-200'):
                            ui.label(event['time']).classes('text-xs text-gray-500 w-20')
                            ui.icon(icon).classes(f'text-sm {color}')
                            ui.label(event['message']).classes('text-sm flex-1')
        
        except Exception as e:
            print(f"Error in update_dashboard: {e}")
    
    ui.timer(0.5, update_ui)
    ui.timer(1.0, update_dashboard)


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


def register_pages(out_queue, ui_queue):
    # Add custom CSS for better toast notifications and blue background
    ui.add_head_html('''
        <style>
            /* Blue gradient background for entire page */
            html, body {
                background: linear-gradient(135deg, #DBEAFE 0%, #BFDBFE 50%, #93C5FD 100%) !important;
                min-height: 100vh !important;
            }
            
            .q-page-container, .nicegui-content, .q-layout {
                background: transparent !important;
            }
            
            .q-page {
                background: transparent !important;
            }
            
            /* Vertical tabs - Orange highlight for active tab */
            .q-tab--active {
                background: linear-gradient(90deg, #FED7AA 0%, #FDBA74 100%) !important;
                border-left: 4px solid #FB923C !important;
                color: #EA580C !important;
                font-weight: 700 !important;
            }
            
            .q-tab {
                border-radius: 8px !important;
                margin: 4px 0 !important;
                transition: all 0.3s ease !important;
            }
            
            .q-tab:hover:not(.q-tab--active) {
                background: rgba(251, 146, 60, 0.1) !important;
            }
            
            .q-tab__icon {
                font-size: 24px !important;
            }
            
            .q-tab__label {
                font-size: 15px !important;
                font-weight: 500 !important;
            }
            
            /* Camera tabs - smaller size */
            .q-card .q-tabs .q-tab {
                font-size: 12px !important;
                padding: 4px 12px !important;
                min-height: 36px !important;
            }
            
            .q-card .q-tabs .q-tab__icon {
                font-size: 16px !important;
            }
            
            .q-card .q-tabs .q-tab__label {
                font-size: 12px !important;
            }
            
            /* Ping Indicator Animation */
            .ping-dot {
                display: inline-block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                margin-right: 8px;
                transition: background-color 0.3s ease;
            }
            
            .ping-online {
                background-color: #4CAF50;
                box-shadow: 0 0 8px #4CAF50;
                animation: pulse-green 2s infinite;
            }
            
            .ping-offline {
                background-color: #F44336;
                box-shadow: 0 0 8px #F44336;
            }
            
            .ping-unknown {
                background-color: #9E9E9E;
            }
            
            @keyframes pulse-green {
                0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
                70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(76, 175, 80, 0); }
                100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
            }
            
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
        # Add blue background to page
        ui.colors(primary='#0ea5e9')  # sky-500
        ui.query('body').classes('bg-gradient-to-br from-blue-100 to-sky-200')
        
        if not app.storage.user.get('logged_in'):
            ui.navigate.to('/login')
        else:
            show_main_ui(out_queue, ui_queue)

    @ui.page('/login')
    def login_page():
        # Add blue background to login page
        ui.query('body').classes('bg-gradient-to-br from-blue-100 to-sky-200')
        login_screen()
