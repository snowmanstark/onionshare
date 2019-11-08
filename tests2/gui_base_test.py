import pytest
import unittest

import json
import os
import requests
import shutil
import base64
import tempfile
import secrets

from PyQt5 import QtCore, QtTest, QtWidgets

from onionshare import strings
from onionshare.common import Common
from onionshare.settings import Settings
from onionshare.onion import Onion
from onionshare.web import Web

from onionshare_gui import Application, MainWindow, GuiCommon
from onionshare_gui.tab.mode.share_mode import ShareMode
from onionshare_gui.tab.mode.receive_mode import ReceiveMode
from onionshare_gui.tab.mode.website_mode import WebsiteMode


class GuiBaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        common = Common(verbose=True)
        qtapp = Application(common)
        common.gui = GuiCommon(common, qtapp, local_only=True)
        cls.gui = MainWindow(common, filenames=None)
        cls.gui.qtapp = qtapp

        # Create some random files to test with
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.tmpfiles = []
        for _ in range(10):
            filename = os.path.join(cls.tmpdir.name, f"{secrets.token_hex(4)}.txt")
            with open(filename, "w") as file:
                file.write(secrets.token_hex(10))
            cls.tmpfiles.append(filename)
        cls.tmpfile_test = os.path.join(cls.tmpdir.name, "test.txt")
        with open(cls.tmpfile_test, "w") as file:
            file.write("onionshare")

    @classmethod
    def tearDownClass(cls):
        # Quit
        QtCore.QTimer.singleShot(0, cls.gui.close_dialog.accept_button.click)
        cls.gui.close()

        cls.gui.cleanup()

    # Shared test methods

    def verify_new_tab(self, tab):
        # Make sure the new tab widget is showing, and no mode has been started
        self.assertTrue(tab.new_tab.isVisible())
        self.assertFalse(hasattr(tab, "share_mode"))
        self.assertFalse(hasattr(tab, "receive_mode"))
        self.assertFalse(hasattr(tab, "website_mode"))

    def new_share_tab(self):
        tab = self.gui.tabs.widget(0)
        self.verify_new_tab(tab)

        # Share files
        tab.share_button.click()
        self.assertFalse(tab.new_tab.isVisible())
        self.assertTrue(tab.share_mode.isVisible())

        return tab

    def new_share_tab_with_files(self):
        tab = self.new_share_tab()

        # Add files
        for filename in self.tmpfiles:
            tab.share_mode.server_status.file_selection.file_list.add_file(filename)

        return tab

    def new_receive_tab(self):
        tab = self.gui.tabs.widget(0)
        self.verify_new_tab(tab)

        # Receive files
        tab.receive_button.click()
        self.assertFalse(tab.new_tab.isVisible())
        self.assertTrue(tab.receive_mode.isVisible())

        return tab

    def new_website_tab(self):
        tab = self.gui.tabs.widget(0)
        self.verify_new_tab(tab)

        # Publish website
        tab.website_button.click()
        self.assertFalse(tab.new_tab.isVisible())
        self.assertTrue(tab.website_mode.isVisible())

        return tab

    def new_website_tab_with_files(self):
        tab = self.new_website_tab()

        # Add files
        for filename in self.tmpfiles:
            tab.website_mode.server_status.file_selection.file_list.add_file(filename)

        return tab

    def close_all_tabs(self):
        for _ in range(self.gui.tabs.count()):
            self.gui.tabs.tabBar().tabButton(0, QtWidgets.QTabBar.RightSide).click()

    def gui_loaded(self):
        """Test that the GUI actually is shown"""
        self.assertTrue(self.gui.show)

    def window_title_seen(self):
        """Test that the window title is OnionShare"""
        self.assertEqual(self.gui.windowTitle(), "OnionShare")

    def server_status_bar_is_visible(self):
        """Test that the status bar is visible"""
        self.assertTrue(self.gui.status_bar.isVisible())

    def mode_settings_widget_is_visible(self, tab):
        """Test that the mode settings are visible"""
        self.assertTrue(tab.get_mode().mode_settings_widget.isVisible())

    def mode_settings_widget_is_hidden(self, tab):
        """Test that the mode settings are hidden when the server starts"""
        self.assertFalse(tab.get_mode().mode_settings_widget.isVisible())

    def click_toggle_history(self, tab):
        """Test that we can toggle Download or Upload history by clicking the toggle button"""
        currently_visible = tab.get_mode().history.isVisible()
        tab.get_mode().toggle_history.click()
        self.assertEqual(tab.get_mode().history.isVisible(), not currently_visible)

    def history_indicator(self, tab, indicator_count="1"):
        """Test that we can make sure the history is toggled off, do an action, and the indiciator works"""
        # Make sure history is toggled off
        if tab.get_mode().history.isVisible():
            tab.get_mode().toggle_history.click()
            self.assertFalse(tab.get_mode().history.isVisible())

        # Indicator should not be visible yet
        self.assertFalse(tab.get_mode().toggle_history.indicator_label.isVisible())

        if type(tab.get_mode()) == ReceiveMode:
            # Upload a file
            files = {"file[]": open(self.tmpfiles[0], "rb")}
            url = f"http://127.0.0.1:{tab.app.port}/upload"
            if tab.settings.get("general", "public"):
                requests.post(url, files=files)
            else:
                requests.post(
                    url,
                    files=files,
                    auth=requests.auth.HTTPBasicAuth(
                        "onionshare", tab.get_mode().web.password
                    ),
                )
            QtTest.QTest.qWait(2000)

        if type(tab.get_mode()) == ShareMode:
            # Download files
            url = f"http://127.0.0.1:{tab.app.port}/download"
            if tab.settings.get("general", "public"):
                requests.get(url)
            else:
                requests.get(
                    url,
                    auth=requests.auth.HTTPBasicAuth(
                        "onionshare", tab.get_mode().web.password
                    ),
                )
            QtTest.QTest.qWait(2000)

        # Indicator should be visible, have a value of "1"
        self.assertTrue(tab.get_mode().toggle_history.indicator_label.isVisible())
        self.assertEqual(
            tab.get_mode().toggle_history.indicator_label.text(), indicator_count
        )

        # Toggle history back on, indicator should be hidden again
        tab.get_mode().toggle_history.click()
        self.assertFalse(tab.get_mode().toggle_history.indicator_label.isVisible())

    def history_is_not_visible(self, tab):
        """Test that the History section is not visible"""
        self.assertFalse(tab.get_mode().history.isVisible())

    def history_is_visible(self, tab):
        """Test that the History section is visible"""
        self.assertTrue(tab.get_mode().history.isVisible())

    def server_working_on_start_button_pressed(self, tab):
        """Test we can start the service"""
        # Should be in SERVER_WORKING state
        tab.get_mode().server_status.server_button.click()
        self.assertEqual(tab.get_mode().server_status.status, 1)

    def toggle_indicator_is_reset(self, tab):
        self.assertEqual(tab.get_mode().toggle_history.indicator_count, 0)
        self.assertFalse(tab.get_mode().toggle_history.indicator_label.isVisible())

    def server_status_indicator_says_starting(self, tab):
        """Test that the Server Status indicator shows we are Starting"""
        self.assertEqual(
            tab.get_mode().server_status_label.text(),
            strings._("gui_status_indicator_share_working"),
        )

    def server_status_indicator_says_scheduled(self, tab):
        """Test that the Server Status indicator shows we are Scheduled"""
        self.assertEqual(
            tab.get_mode().server_status_label.text(),
            strings._("gui_status_indicator_share_scheduled"),
        )

    def server_is_started(self, tab, startup_time=2000):
        """Test that the server has started"""
        QtTest.QTest.qWait(startup_time)
        # Should now be in SERVER_STARTED state
        self.assertEqual(tab.get_mode().server_status.status, 2)

    def web_server_is_running(self, tab):
        """Test that the web server has started"""
        try:
            requests.get(f"http://127.0.0.1:{tab.app.port}/")
            self.assertTrue(True)
        except requests.exceptions.ConnectionError:
            self.assertTrue(False)

    def have_a_password(self, tab):
        """Test that we have a valid password"""
        if not tab.settings.get("general", "public"):
            self.assertRegex(tab.get_mode().server_status.web.password, r"(\w+)-(\w+)")
        else:
            self.assertIsNone(tab.get_mode().server_status.web.password, r"(\w+)-(\w+)")

    def add_button_visible(self, tab):
        """Test that the add button should be visible"""
        self.assertTrue(
            tab.get_mode().server_status.file_selection.add_button.isVisible()
        )

    def url_description_shown(self, tab):
        """Test that the URL label is showing"""
        self.assertTrue(tab.get_mode().server_status.url_description.isVisible())

    def have_copy_url_button(self, tab):
        """Test that the Copy URL button is shown and that the clipboard is correct"""
        self.assertTrue(tab.get_mode().server_status.copy_url_button.isVisible())

        tab.get_mode().server_status.copy_url_button.click()
        clipboard = tab.common.gui.qtapp.clipboard()
        if tab.settings.get("general", "public"):
            self.assertEqual(clipboard.text(), f"http://127.0.0.1:{tab.app.port}")
        else:
            self.assertEqual(
                clipboard.text(),
                f"http://onionshare:{tab.get_mode().server_status.web.password}@127.0.0.1:{tab.app.port}",
            )

    def server_status_indicator_says_started(self, tab):
        """Test that the Server Status indicator shows we are started"""
        if type(tab.get_mode()) == ReceiveMode:
            self.assertEqual(
                tab.get_mode().server_status_label.text(),
                strings._("gui_status_indicator_receive_started"),
            )
        if type(tab.get_mode()) == ShareMode:
            self.assertEqual(
                tab.get_mode().server_status_label.text(),
                strings._("gui_status_indicator_share_started"),
            )

    def web_page(self, tab, string):
        """Test that the web page contains a string"""

        url = f"http://127.0.0.1:{tab.app.port}/"
        if tab.settings.get("general", "public"):
            r = requests.get(url)
        else:
            r = requests.get(
                url,
                auth=requests.auth.HTTPBasicAuth(
                    "onionshare", tab.get_mode().web.password
                ),
            )

        self.assertTrue(string in r.text)

    def history_widgets_present(self, tab):
        """Test that the relevant widgets are present in the history view after activity has taken place"""
        self.assertFalse(tab.get_mode().history.empty.isVisible())
        self.assertTrue(tab.get_mode().history.not_empty.isVisible())

    def counter_incremented(self, tab, count):
        """Test that the counter has incremented"""
        self.assertEqual(tab.get_mode().history.completed_count, count)

    def stop_running_server(self, tab):
        """Stop a server that's running"""
        self.assertNotEqual(tab.get_mode().server_status.status, 0)

        tab.get_mode().server_status.server_button.click()
        QtTest.QTest.qWait(200)

        self.server_is_stopped(tab)
        self.web_server_is_stopped(tab)

    def server_is_stopped(self, tab):
        """Test that the server stops when we click Stop"""
        if (
            type(tab.get_mode()) == ReceiveMode
            or (
                type(tab.get_mode()) == ShareMode
                and not tab.settings.get("share", "autostop_sharing")
            )
            or (type(tab.get_mode()) == WebsiteMode)
        ):
            tab.get_mode().server_status.server_button.click()
        self.assertEqual(tab.get_mode().server_status.status, 0)

    def web_server_is_stopped(self, tab):
        """Test that the web server also stopped"""
        QtTest.QTest.qWait(200)

        try:
            requests.get(f"http://127.0.0.1:{tab.app.port}/")
            self.assertTrue(False)
        except requests.exceptions.ConnectionError:
            self.assertTrue(True)

    def server_status_indicator_says_closed(self, tab):
        """Test that the Server Status indicator shows we closed"""
        if type(tab.get_mode()) == ReceiveMode:
            self.assertEqual(
                tab.get_mode().server_status_label.text(),
                strings._("gui_status_indicator_receive_stopped"),
            )
        if type(tab.get_mode()) == ShareMode:
            if tab.settings.get("share", "autostop_sharing"):
                self.assertEqual(
                    tab.get_mode().server_status_label.text(),
                    strings._("gui_status_indicator_share_stopped"),
                )
            else:
                self.assertEqual(
                    tab.get_mode().server_status_label.text(),
                    strings._("closing_automatically"),
                )

    def clear_all_history_items(self, tab, count):
        if count == 0:
            tab.get_mode().history.clear_button.click()
        self.assertEquals(len(tab.get_mode().history.item_list.items.keys()), count)

    # Auto-stop timer tests
    def set_timeout(self, tab, timeout):
        """Test that the timeout can be set"""
        timer = QtCore.QDateTime.currentDateTime().addSecs(timeout)
        tab.get_mode().mode_settings_widget.autostop_timer_widget.setDateTime(timer)
        self.assertTrue(
            tab.get_mode().mode_settings_widget.autostop_timer_widget.dateTime(), timer
        )

    def autostop_timer_widget_hidden(self, tab):
        """Test that the auto-stop timer widget is hidden when share has started"""
        self.assertFalse(
            tab.get_mode().mode_settings_widget.autostop_timer_container.isVisible()
        )

    def server_timed_out(self, tab, wait):
        """Test that the server has timed out after the timer ran out"""
        QtTest.QTest.qWait(wait)
        # We should have timed out now
        self.assertEqual(tab.get_mode().server_status.status, 0)

    # Grouped tests follow from here

    def run_all_common_setup_tests(self):
        self.gui_loaded()
        self.window_title_seen()
        self.server_status_bar_is_visible()
