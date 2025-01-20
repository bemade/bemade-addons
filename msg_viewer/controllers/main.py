import base64
import logging
import os
from contextlib import nullcontext

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request, Response, Stream
from odoo.tools import str2bool, file_open

_logger = logging.getLogger(__name__)

class MsgViewer(http.Controller):
    @http.route([
        '/msg_viewer/content',
        '/msg_viewer/content/<string:xmlid>',
        '/msg_viewer/content/<string:xmlid>/<string:filename>',
        '/msg_viewer/content/<int:id>',
        '/msg_viewer/content/<int:id>/<string:filename>',
        '/msg_viewer/content/<string:model>/<int:id>/<string:field>',
        '/msg_viewer/content/<string:model>/<int:id>/<string:field>/<string:filename>',
    ], type='http', auth='public', readonly=True)
    def msg_content(self, xmlid=None, model='ir.attachment', id=None, field='raw',
                   filename=None, filename_field='name', download=False, access_token=None):
        """Serve the MSG file content.
        
        This endpoint serves the raw MSG file which will be processed by the msg-viewer JavaScript library.
        """
        try:
            record = request.env['ir.binary']._find_record(xmlid, model, id and int(id), access_token, field=field)
            
            # Get the binary content
            content = record[field]
            if not content:
                return request.not_found()
            
            # Convert base64 to binary if needed
            if isinstance(content, str):
                content = base64.b64decode(content)
            
            # Create a stream to serve the file
            stream = Stream.from_bytes(content)
            stream.type = 'application/vnd.ms-outlook'  # MIME type for .msg files
            
            return stream.get_response(as_attachment=str2bool(download))
                
        except (AccessError, UserError):
            return request.not_found()
        except Exception as e:
            _logger.exception("Error while serving MSG file")
            return Response(
                f"Error serving MSG file: {str(e)}",
                status=500
            )

    @http.route('/msg_viewer/content', type='http', auth='user')
    def get_msg_content(self, model, field, id, **kwargs):
        """Get the content of a MSG file."""
        record = request.env[model].browse(int(id))
        if not record.exists() or not hasattr(record, field):
            return Response(status=404)

        field_value = getattr(record, field)
        if not field_value:
            return Response(status=404)

        return Response(
            field_value,
            headers=[
                ('Content-Type', 'application/vnd.ms-outlook'),
                ('Content-Disposition', f'inline; filename="{record.name}"'),
            ]
        )

    @http.route('/msg_viewer/static/lib/<path:path>', type='http', auth='public')
    def get_static_lib(self, path):
        """Serve static files from the lib directory."""
        addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(addon_path, 'static', 'src', 'lib', path)
        
        try:
            with file_open(file_path, 'rb') as f:
                content = f.read()
        except (IOError, OSError):
            return Response(status=404)

        content_type = 'text/javascript' if path.endswith('.js') else 'text/css' if path.endswith('.css') else 'text/html'
        return Response(content, content_type=content_type)
