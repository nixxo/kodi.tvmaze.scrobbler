# coding: utf-8
# (c) Roman Miroshnychenko <roman1972@gmail.com> 2020
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""GUI-related classes and functions"""
# pylint: disable=missing-docstring
from __future__ import absolute_import, unicode_literals

import threading
import weakref
from contextlib import contextmanager

import pyxbmct
from kodi_six import xbmc
from kodi_six.xbmcgui import Dialog, DialogProgressBG
from six import text_type

from .kodi_service import GETTEXT as _
from .tvmaze_api import poll_authorization, AuthorizationError

try:
    from typing import Text, Generator  # pylint: disable=unused-import
except ImportError:
    pass

DIALOG = Dialog()


class ConfirmationLoop(threading.Thread):
    def __init__(self, parent_window, token):
        # type: (ConfirmationDialog, Text) -> None
        super(ConfirmationLoop, self).__init__()
        self._parent_window = weakref.proxy(parent_window)  # type: ConfirmationDialog
        self._token = token
        self.username = ''
        self.apikey = ''
        self.error_message = None
        self._monitor = xbmc.Monitor()
        self.stop_event = threading.Event()

    def run(self):
        self.stop_event.clear()
        while not self.stop_event.is_set():
            xbmc.sleep(10000)
            if self._monitor.abortRequested():
                break
            try:
                result = poll_authorization(self._token)
            except AuthorizationError as exc:
                self.error_message = text_type(exc)
                break
            else:
                if result is None:
                    continue
                self.username, self.apikey = result
                break
        self._parent_window.close()


class ConfirmationDialog(pyxbmct.AddonDialogWindow):
    def __init__(self, email, token, confirm_url, qrcode_path):
        # type: (Text, Text, Text, Text) -> None
        super(ConfirmationDialog, self).__init__(_('Confirm Addon Authorization'))
        self._email = email
        self._confirm_url = confirm_url
        self._qrcode_path = qrcode_path
        self.is_confirmed = False
        self.username = ''
        self.apikey = ''
        self.error_message = None
        self._confirmation_loop = ConfirmationLoop(self, token)
        self.setGeometry(600, 600, 7, 5)
        self._set_controls()
        self._set_connections()

    def _set_controls(self):
        textbox = pyxbmct.TextBox()
        self.placeControl(textbox, 0, 0, 2, 5)
        textbox.setText(_(
            'To authorize the addon open the link below[CR]'
            '[B]{confirm_url}[/B][CR]'
            'or check your mailbox[CR][B]{email}[/B]').format(
                confirm_url=self._confirm_url,
                email=self._email))
        qr_code = pyxbmct.Image(self._qrcode_path)
        self.placeControl(qr_code, 2, 1, 4, 3, pad_x=0)
        self._cancel_btn = pyxbmct.Button(_('Cancel'))
        self.placeControl(self._cancel_btn, 6, 2, pad_x=-5, pad_y=10)
        self.setFocus(self._cancel_btn)

    def _set_connections(self):
        self.connect(pyxbmct.ACTION_NAV_BACK, self._cancel)
        self.connect(self._cancel_btn, self._cancel)

    def doModal(self):
        self._confirmation_loop.start()
        super(ConfirmationDialog, self).doModal()
        self.username = self._confirmation_loop.username
        self.apikey = self._confirmation_loop.apikey
        self.error_message = self._confirmation_loop.error_message
        if self.username and self.apikey and self.error_message is None:
            self.is_confirmed = True

    def _cancel(self):
        self._confirmation_loop.stop_event.set()
        self._confirmation_loop.join()
        self.close()


@contextmanager
def background_progress_dialog(heading, message):
    # type: (Text, Text) -> Generator[DialogProgressBG, None, None]
    dialog = DialogProgressBG()
    dialog.create(heading, message)
    try:
        yield dialog
    finally:
        dialog.close()
