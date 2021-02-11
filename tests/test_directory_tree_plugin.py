import platform
import shutil
import subprocess

import pytest

from porcupine import get_paned_window, tabs, utils
from porcupine.plugins import directory_tree as plugin_module
from porcupine.plugins.directory_tree import DirectoryTree


@pytest.fixture
def tree():
    [tree] = [w for w in utils.get_children_recursively(get_paned_window()) if isinstance(w, DirectoryTree)]
    yield tree
    for child in tree.get_children(''):
        tree.delete(child)


def test_adding_nested_projects(tree, tmp_path):
    def get_paths():
        return [tree.get_path(project) for project in tree.get_children()]

    (tmp_path / 'a' / 'b').mkdir(parents=True)
    assert get_paths() == []
    tree.add_project(tmp_path / 'a')
    assert get_paths() == [tmp_path / 'a']
    tree.add_project(tmp_path / 'a' / 'b')
    assert get_paths() == [tmp_path / 'a']
    tree.add_project(tmp_path)
    assert get_paths() == [tmp_path]


@pytest.mark.skipif(platform.system() == 'Windows', reason="rmtree can magically fail on windows")
def test_deleting_project(tree, tmp_path, tabmanager, monkeypatch):
    def get_project_names():
        return [tree.get_path(project).name for project in tree.get_children()]

    (tmp_path / 'a').mkdir(parents=True)
    (tmp_path / 'b').mkdir(parents=True)
    (tmp_path / 'a' / 'README').touch()
    (tmp_path / 'b' / 'README').touch()
    a_tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'a' / 'README')
    b_tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'b' / 'README')

    tabmanager.add_tab(a_tab)
    assert get_project_names() == ['a']
    tabmanager.close_tab(a_tab)
    shutil.rmtree(tmp_path / 'a')
    tabmanager.add_tab(b_tab)
    assert get_project_names() == ['b']
    tabmanager.close_tab(b_tab)


def test_autoclose(tree, tmp_path, tabmanager, monkeypatch):
    def get_project_names():
        return [tree.get_path(project).name for project in tree.get_children()]

    (tmp_path / 'a').mkdir(parents=True)
    (tmp_path / 'b').mkdir(parents=True)
    (tmp_path / 'c').mkdir(parents=True)
    (tmp_path / 'a' / 'README').touch()
    (tmp_path / 'b' / 'README').touch()
    (tmp_path / 'c' / 'README').touch()
    a_tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'a' / 'README')
    b_tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'b' / 'README')
    c_tab = tabs.FileTab.open_file(tabmanager, tmp_path / 'c' / 'README')
    monkeypatch.setattr(plugin_module, 'PROJECT_AUTOCLOSE_COUNT', 2)

    assert get_project_names() == []

    tabmanager.add_tab(a_tab)
    assert get_project_names() == ['a']
    tabmanager.add_tab(b_tab)
    assert get_project_names() == ['b', 'a']
    tabmanager.add_tab(c_tab)
    assert get_project_names() == ['c', 'b', 'a']

    tabmanager.close_tab(b_tab)
    assert get_project_names() == ['c', 'a']
    tabmanager.close_tab(c_tab)
    assert get_project_names() == ['c', 'a']
    tabmanager.close_tab(a_tab)
    assert get_project_names() == ['c', 'a']


@pytest.mark.skipif(shutil.which('git') is None, reason="git not found")
def test_added_and_modified_content(tree, tmp_path, monkeypatch):
    def dont_actually_run_in_thread(blocking_function, done_callback, check_interval_ms=1):
        done_callback(True, blocking_function())
    monkeypatch.setattr(utils, 'run_in_thread', dont_actually_run_in_thread)

    subprocess.check_call(['git', 'init'], cwd=tmp_path, stdout=subprocess.DEVNULL)
    tree.add_project(tmp_path)

    (tmp_path / 'a').write_text('a')
    (tmp_path / 'b').write_text('b')
    subprocess.check_call(['git', 'add', 'a', 'b'], cwd=tmp_path)
    (tmp_path / 'b').write_text('lol')
    [project_id] = tree.get_children()

    tree.refresh_everything()
    assert set(tree.item(project_id, 'tags')) == {'project', 'dir', 'git_modified'}

    subprocess.check_call(['git', 'add', 'a', 'b'], cwd=tmp_path)
    tree.refresh_everything()
    assert set(tree.item(project_id, 'tags')) == {'project', 'dir', 'git_added'}