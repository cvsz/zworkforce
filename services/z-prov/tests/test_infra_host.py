import json
from types import SimpleNamespace

import pytest
from zeaz_infra.host import HostDetector, HostInventory


def _host_tree(tmp_path, *, vendor: str | None = None, nvidia: bool = False):
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    dev = tmp_path / "dev"
    (proc / "driver" / "nvidia").mkdir(parents=True)
    (sys / "class" / "dmi" / "id").mkdir(parents=True)
    (sys / "class" / "drm").mkdir(parents=True)
    dev.mkdir()
    (proc / "cpuinfo").write_text(
        "processor\t: 0\nmodel name\t: Test CPU\nflags\t: fpu hypervisor\n"
    )
    (proc / "meminfo").write_text("MemTotal:       1048576 kB\n")
    (sys / "class" / "dmi" / "id" / "sys_vendor").write_text("VMware, Inc.")
    (sys / "class" / "dmi" / "id" / "product_name").write_text("VMware Virtual Platform")
    if nvidia:
        (proc / "driver" / "nvidia" / "version").write_text("NVIDIA test driver")
    if vendor:
        card = sys / "class" / "drm" / "card0"
        (card / "device").mkdir(parents=True)
        (card / "device" / "vendor").write_text(vendor)
    return proc, sys, dev


def test_host_detector_selects_nvidia_and_vmware_without_mutation(tmp_path, monkeypatch):
    proc, sys, dev = _host_tree(tmp_path, vendor="0x10de", nvidia=True)
    monkeypatch.setattr("zeaz_infra.host.os.cpu_count", lambda: 8)
    monkeypatch.setattr(
        "zeaz_infra.host.shutil.disk_usage",
        lambda path: SimpleNamespace(total=1000, used=400, free=600),
    )
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    result = HostDetector(proc_root=proc, sys_root=sys, dev_root=dev, disk_path=tmp_path).detect()
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert result.install_mode == "nvidia"
    assert result.gpu_vendor == "nvidia"
    assert result.virtualization == "vmware"
    assert result.memory_bytes == 1048576 * 1024
    assert result.disk_free_bytes == 600
    assert before == after
    plan = HostDetector(proc_root=proc, sys_root=sys, dev_root=dev, disk_path=tmp_path).plan(result)
    assert plan.package_sources == ("docker-official-apt",)
    assert "nvidia-container-toolkit" in plan.optional_packages
    assert "open-vm-tools" in plan.optional_packages
    assert [step.name for step in plan.steps] == [
        "detect-host",
        "install-docker-engine",
        "configure-nvidia-container-toolkit",
        "preserve-vmware-integration",
        "apply-kernel-tuning",
        "configure-ufw",
        "install-systemd-services",
        "verify-backup-update-rollback",
        "install-uninstall-path",
    ]


def test_host_detector_selects_amd_and_cpu_only(tmp_path, monkeypatch):
    proc, sys, dev = _host_tree(tmp_path, vendor="0x1002")
    monkeypatch.setattr(
        "zeaz_infra.host.shutil.disk_usage",
        lambda path: SimpleNamespace(total=10, used=5, free=5),
    )
    amd = HostDetector(proc_root=proc, sys_root=sys, dev_root=dev, disk_path=tmp_path).detect()
    assert amd.install_mode == "amd"
    assert amd.gpu_vendor == "amd"
    amd_plan = HostDetector(proc_root=proc, sys_root=sys, dev_root=dev, disk_path=tmp_path).plan(amd)
    assert "nvidia-container-toolkit" not in amd_plan.optional_packages
    assert any(step.name == "skip-nvidia-toolkit" for step in amd_plan.steps)

    cpu_proc, cpu_sys, cpu_dev = _host_tree(tmp_path / "cpu")
    cpu = HostDetector(proc_root=cpu_proc, sys_root=cpu_sys, dev_root=cpu_dev, disk_path=tmp_path).detect()
    assert cpu.install_mode == "cpu-only"
    assert cpu.gpu_vendor == "none"
    cpu_plan = HostDetector(
        proc_root=cpu_proc,
        sys_root=cpu_sys,
        dev_root=cpu_dev,
        disk_path=tmp_path / "cpu",
    ).plan(cpu)
    assert "nvidia-container-toolkit" not in cpu_plan.optional_packages
    assert any(step.name == "cpu-only-mode" for step in cpu_plan.steps)


def test_host_detector_rejects_relative_roots_and_json_round_trip(tmp_path):
    with pytest.raises(ValueError):
        HostDetector(proc_root=tmp_path.relative_to(tmp_path))
    proc, sys, dev = _host_tree(tmp_path)
    value = HostDetector(proc_root=proc, sys_root=sys, dev_root=dev, disk_path=tmp_path).detect()
    encoded = json.dumps(value.model_dump(mode="json"))
    assert HostInventory.model_validate(json.loads(encoded)) == value
