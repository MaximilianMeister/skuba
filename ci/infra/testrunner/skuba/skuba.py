import logging
import os
import platforms
import shutil

from utils.format import Format
from utils.utils import (step, Utils)

logger = logging.getLogger('testrunner')

class Skuba:

    def __init__(self, conf, platform):
        self.conf = conf
        self.binpath = self.conf.skuba.binpath
        self.utils = Utils(self.conf)
        self.platform = platforms.get_platform(conf, platform)
        self.cwd = "{}/test-cluster".format(self.conf.workspace)

    def _verify_skuba_bin_dependency(self):
        if not os.path.isfile(self.binpath):
            raise FileNotFoundError("skuba not found at {}".format(self.binpath))

    def _verify_bootstrap_dependency(self):
        if not os.path.exists(os.path.join(self.conf.workspace, "test-cluster")):
            raise Exception("test-cluster not found. Please run bootstrap and try again")

    @staticmethod
    @step
    def build(conf):
        """Builds skuba from source"""
        utils = Utils(conf)
        go_dir = os.path.join(conf.workspace, "go")
        src_dir = os.path.join(go_dir, "src/github.com/SUSE")

        # Make a fresh copy of the source code
        utils.cleanup_file(go_dir)
        os.makedirs(src_dir, exist_ok=True)
        shutil.copytree(conf.skuba.srcpath, os.path.join(src_dir, os.path.basename(conf.skuba.srcpath)))

        utils.gorun("go version")
        utils.gorun("make")

    @staticmethod
    @step
    def cleanup(conf):
        """Cleanup skuba working environment"""

        # TODO: check why (and if) the following command is needed
        # This is pretty aggressive but modules are also present
        # in workspace and they lack the 'w' bit so just set
        # everything so we can do whatever we want during cleanup
        Utils.chmod_recursive(conf.workspace, 0o777)

        dirs = [os.path.join(conf.workspace, "test-cluster"),
                os.path.join(conf.workspace, "go"),
                os.path.join(conf.workspace, "logs"),
                #TODO: move this to utils as ssh_cleanup
                os.path.join(conf.workspace, "ssh-agent-sock")]

        Utils.cleanup_files(dirs)

    @step
    def cluster_init(self, kubernetes_version=None):
        logger.debug("Cleaning up any previous test-cluster dir")
        self.utils.cleanup_file(self.cwd)

        k8s_version_option = ""
        if kubernetes_version:
           k8s_version_option = "--kubernetes-version {}".format(kubernetes_version)
        cmd = "cluster init --control-plane {} {} test-cluster".format(
                   self.platform.get_lb_ipaddr(), k8s_version_option)
        # Override work directory, because init must run in the parent directory of the
        # cluster directory
        self._run_skuba(cmd, cwd=self.conf.workspace)

    @step
    def node_bootstrap(self):
        self._verify_bootstrap_dependency()

        master0_ip = self.platform.get_nodes_ipaddrs("master")[0]
        cmd = "node bootstrap --user {username} --sudo --target \
                 {ip} my-master-0".format(ip=master0_ip, username=self.conf.nodeuser)
        self._run_skuba(cmd)

    @step
    def node_join(self, role="worker", nr=0):
        self._verify_bootstrap_dependency()

        ip_addrs = self.platform.get_nodes_ipaddrs(role)

        if nr < 0:
            raise ValueError("Node number cannot be negative")

        if nr >= len(ip_addrs):
            raise Exception(Format.alert("Node {role}-{nr} no deployed in "
                      "infrastructure".format(role=role, nr=nr)))

        cmd = "node join --role {role} --user {username} --sudo --target {ip} \
               my-{role}-{nr}".format(role=role, ip=ip_addrs[nr], nr=nr,
                                   username=self.conf.nodeuser)
        try:
            self._run_skuba(cmd)
        except Exception as ex:
            raise Exception("Error executing cmd {}") from ex

    @step
    def node_remove(self, role="worker", nr=0):
        self._verify_bootstrap_dependency()

        if role not in ("master", "worker"):
            raise ValueError("Invalid role {}".format(role))

        n_nodes = self.num_of_nodes(role)

        if nr < 0:
            raise ValueError("Node number must be non negative")

        if nr >= n_nodes:
            raise ValueError("Error: there is no {role}-{nr} \
                              node to remove from cluster".format(role=role, nr=nr))

        cmd = "node remove my-{role}-{nr}".format(role=role, nr=nr)

        try:
            self._run_skuba(cmd)
        except Exception as ex:
            raise Exception("Error executing cmd {}".format(cmd)) from ex

    @step
    def node_upgrade(self, action, role, nr):
        self._verify_bootstrap_dependency()

        if role not in ("master", "worker"):
            raise ValueError("Invalid role '{}'".format(role))

        if nr >= self.num_of_nodes(role):
            raise ValueError("Error: there is no {}-{} \
                              node in the cluster".format(role, nr))

        if action == "plan":
            cmd = "node upgrade plan my-{}-{}".format(role, nr)
        elif action == "apply":
            ip_addrs = self.platform.get_nodes_ipaddrs(role)
            cmd = "node upgrade apply --user {username} --sudo --target {ip}".format(
                ip=ip_addrs[nr], username=self.conf.nodeuser)
        else:
            raise ValueError("Invalid action '{}'".format(action))

        return self._run_skuba(cmd)

    @step
    def cluster_upgrade_plan(self):
        self._verify_bootstrap_dependency()
        return self._run_skuba("cluster upgrade plan")

    @step
    def cluster_status(self):
        self._verify_bootstrap_dependency()
        return self._run_skuba("cluster status")

    @step
    def num_of_nodes(self, role):

        if role not in ("master", "worker"):
            raise ValueError("Invalid role '{}'".format(role))

        test_cluster = os.path.join(self.conf.workspace, "test-cluster")
        cmd = "cd " + test_cluster + "; " + self.binpath + " cluster status"
        output = self.utils.runshellcommand(cmd)
        return output.count(role)

    def _run_skuba(self, cmd, cwd=None):
        """Running skuba command in cwd.
        The cwd defautls to {workspace}/test-cluster but can be overrided
        for example, for the init command that must run in {workspace}
        """
        self._verify_skuba_bin_dependency()

        if cwd is None:
           cwd=self.cwd

        env = {"SSH_AUTH_SOCK": os.path.join(self.conf.workspace, "ssh-agent-sock")}

        return self.utils.runshellcommand(self.binpath + " "+ cmd, cwd=cwd, env=env)
