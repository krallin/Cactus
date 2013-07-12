#coding:utf-8
import os
import shutil
import tempfile
import hashlib

import mock
from cactus.deployment import BaseDeploymentEngine

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from cactus.config.router import ConfigRouter
from cactus.deployment.file import BaseFile
from cactus.plugin.builtin.cache import CacheDurationPlugin
from cactus.plugin.loader import ObjectsPluginLoader
from cactus.plugin.manager import PluginManager


class TestHeadersPlugin(object):
    """
    An utility plugin to retrieve a file's header.
    """
    def __init__(self):
        self.headers = None

    def preDeployFile(self, file):
        self.headers = file.headers


class TestFile(BaseFile):
    def remote_changed(self):
        return True

    def do_upload(self):
        pass


class TestDeployFile(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.build_path = os.path.join(self.test_dir, '.build')
        os.mkdir(self.build_path)


        self.site = mock.MagicMock()
        self.site.plugin_manager = PluginManager(self.site, [])
        self.site.path = self.test_dir
        self.site.config = ConfigRouter([os.path.join(self.test_dir, "config.json")])
        self.site.config.set("site-url", "http://example.com")

        self.engine = BaseDeploymentEngine(self.site)


    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_cache_control(self):
        """
        Ensure that the Cache control headers are properly set
        """
        # Test a fingerprinted file
        content = 'abc'
        h = hashlib.md5(content).hexdigest()
        filename = "file.{0}.data".format(h)

        with open(os.path.join(self.build_path,  filename), "w") as f:
            f.write(content)

        p = TestHeadersPlugin()
        self.site.plugin_manager.loaders = [ObjectsPluginLoader([p, CacheDurationPlugin()])]
        self.site.plugin_manager.reload()
        self.site.plugin_manager.preDeploy(self.site)

        f = TestFile(self.engine, filename)
        f.upload()

        self.assertIn("cache-control", p.headers)
        cache_control = p.headers["cache-control"]
        self.assertTrue(cache_control.startswith('max-age='))
        self.assertEqual(int(cache_control.split('=')[1]), f.MAX_CACHE_EXPIRATION)


        # Test a non fingerprinted file
        with open(os.path.join(self.build_path, "123.html"), "w") as f:
            f.write("abc")

        # Prepare setup
        p = TestHeadersPlugin()
        self.site.plugin_manager.loaders = [ObjectsPluginLoader([p, CacheDurationPlugin()])]
        self.site.plugin_manager.reload()
        f = TestFile(self.engine, "123.html")

        # Test with no configured cache duration
        self.site.config.set("cache-duration", None)
        self.site.plugin_manager.preDeploy(self.site)

        f.upload()
        self.assertIn("cache-control", p.headers)
        cache_control = p.headers["cache-control"]
        self.assertTrue(cache_control.startswith('max-age='))
        self.assertEqual(int(cache_control.split('=')[1]), f.DEFAULT_CACHE_EXPIRATION)

        # Test with a configured cache duration
        self.site.config.set("cache-duration", 123)
        self.site.plugin_manager.preDeploy(self.site)

        f.upload()
        self.assertIn("cache-control", p.headers)
        cache_control = p.headers["cache-control"]
        self.assertTrue(cache_control.startswith('max-age='))
        self.assertEqual(int(cache_control.split('=')[1]), 123)
