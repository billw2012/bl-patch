import os
from lxml import etree
from copy import deepcopy

BASE_MODULES = [
    'Native',
    'SandBoxCore',
    'SandBox',
    'CustomBattle',
    'StoryMode'
]
SP_ITEMS_REL_PATH = 'SandBoxCore\\ModuleData\\spitems.xml'


def items_from_submodule(file):
    root = etree.parse(file).getroot()
    items = []
    submodule_root = os.path.dirname(file)
    for xmlname in root.iter('XmlName'):
        if(xmlname.get('id') == 'Items'):
            items.append(os.path.join(submodule_root,
                                      'ModuleData',
                                      xmlname.get('path') + '.xml'))
    return items


PATCH_NAME = 'zzzzMergedPatch'

SUBMODULE_TEMPLATE = '''
<Module>
    <Name value="" />
    <Id value="" />
    <Version value="v1.4.0" />
    <SingleplayerModule value="true" />
    <MultiplayerModule value="false" />
    <Official value="false" />
    <DependedModules/>
    <SubModules/>
    <Xmls>
        <XmlNode>
            <XmlName id="Items" path="patchitems" />
            <IncludedGameTypes>
                <Gametype value="Campaign" />
                <Gametype value="CampaignStoryMode" />
                <GameType value="CustomGame" />
            </IncludedGameTypes>
        </XmlNode>
    </Xmls>
</Module>
'''


def main():
    import argparse
    from xmldiff import main as xmldiffmain

    parser = argparse.ArgumentParser(
        description='Generate a merged items patch mod for Mound & Blade II: Bannerlord')
    parser.add_argument('--base', type=str, help='Bannerlord directory',
                        default='C:\\Program Files (x86)\\Steam\\steamapps\\common\\Mount & Blade II Bannerlord')
    parser.add_argument('--verbose', type=bool, help='Verbose logging, includes each detected change in each item',
                        default=False)
    parser.add_argument('mods', type=str, nargs='*',
                        help='List of mods to generate patch from, in load order. Defaults to reading LauncherData.xml')
    args = parser.parse_args()
    if not os.path.isdir(args.base):
        print(f"{args.base} doesn't appear to be a valid directory")
        pass
    modulesdir = os.path.join(args.base, 'Modules')
    basespitems = os.path.join(modulesdir, SP_ITEMS_REL_PATH)
    if not os.path.isfile(basespitems):
        print(f"{basespitems} doesn't exist")
        return 2
    print(f'Loading base spitems from {basespitems} ... ', end='')
    itemsbase = etree.parse(basespitems).getroot()
    print('done')

    itemspatched = deepcopy(itemsbase)

    patcher = CustomPatcher()

    # https://stackoverflow.com/a/30924555/6402065
    launcherDataXmlPath = get_launcher_xml_path()
    if not os.path.isfile(launcherDataXmlPath):
        print(
            f"Couldn't find Launcher config at {launcherDataXmlPath}. Run the launcher to generate it.")
        return 3
    # os.path.expanduser('~\Configs\LauncherData.xml')
    launcherData = etree.parse(launcherDataXmlPath).getroot()
    spdata = launcherData.find('SingleplayerData').find('ModDatas')

    mods = args.mods
    if len(mods) == 0:
        for mod in spdata:
            if mod.find('IsSelected').text != 'true':
                continue
            id = mod.find('Id').text
            if id == PATCH_NAME:
                continue
            submodxmlpath = os.path.join(modulesdir, id, 'SubModule.xml')
            if not os.path.isfile(submodxmlpath):
                print(f'Warning: {submodxmlpath} not found')
                continue
            subxml = etree.parse(submodxmlpath).getroot()
            off = subxml.find('Official')
            # Only non official mods of course
            if off is None or off.attrib['value'] != 'true':
                mods.append(id)

    for mod in mods:
        print(f'Patching items from {mod}:')
        for itemsxmlpath in items_from_submodule(os.path.join(modulesdir, mod, 'SubModule.xml')):
            itemsxml = etree.parse(itemsxmlpath).getroot()
            for item in itemsxml.iter('Item'):
                id = item.get('id')
                print(f'  {id} ... ', end='')
                baseitem = itemsbase.find(f".//Item[@id='{id}']")
                if(baseitem is None):
                    # If we don't find it we can just clone it as is
                    print('added')
                    itemspatched.append(deepcopy(item))
                    # We will use this as the base item for further patching as well
                    itemsbase.append(deepcopy(item))
                else:
                    # Merge using base item
                    print('merged')
                    # Make new empty trees to do the diff in
                    baseitemdt = etree.Element('Items')
                    baseitemdt.append(deepcopy(baseitem))
                    itemdt = etree.Element('Items')
                    itemdt.append(deepcopy(item))
                    diff = xmldiffmain.diff_trees(baseitemdt, itemdt)

                    if(args.verbose):
                        for d in diff:
                            print(f'    {d}')

                    # Apply the diff
                    # Take the existing patched item
                    oldpatcheditem = itemspatched.find(f".//Item[@id='{id}']")
                    itemspatched.remove(oldpatcheditem)
                    # Make new tree to do the patching in, with only the existing patched item in it
                    mergedt = etree.Element('Items')
                    mergedt.append(oldpatcheditem)
                    # Do the patching
                    patcher.patch_in_place(diff, mergedt)
                    # Put the result back into the real patched items tree
                    itemspatched.append(deepcopy(mergedt.find('Item')))

    export_module(modulesdir, PATCH_NAME,
                  BASE_MODULES + args.mods, itemspatched)

    print('Updating LauncherData.xml ... ')
    # Remove any existing LauncherData entry so we can readd at the end
    for patchIdNode in spdata.xpath(f'.//Id[text()="{PATCH_NAME}"]'):
        patchNode = patchIdNode.getparent()
        patchNode.getparent().remove(patchNode)

    patchNode = etree.SubElement(spdata, 'UserModData')
    etree.SubElement(patchNode, 'Id').text = PATCH_NAME
    etree.SubElement(patchNode, 'IsSelected').text = 'true'

    # os.remove(launcherDataXmlPath)

    etree.ElementTree(launcherData).write(launcherDataXmlPath,
                                          encoding='utf-8',
                                          xml_declaration=True,
                                          pretty_print=True)

    print('DONE!')

    return 0


def get_launcher_xml_path():
    # https://stackoverflow.com/a/30924555/6402065
    import ctypes.wintypes
    CSIDL_PERSONAL = 5       # My Documents
    SHGFP_TYPE_CURRENT = 0   # Get current, not default value
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(
        None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)

    print('No mod list specified, reading LauncherData.xml to determine mod list and order')
    launcherDataXmlPath = os.path.join(
        buf.value, 'Mount and Blade II Bannerlord', 'Configs', 'LauncherData.xml')
    return launcherDataXmlPath


def export_module(modulesdir, modulename, dependencies, itemspatched):
    import datetime
    import shutil

    outdir = os.path.join(modulesdir, modulename)
    if os.path.exists(outdir):
        print('Removing existing patch mod')
        shutil.rmtree(outdir)

    print(f'Writing new patch mod {modulename}')
    modulexml = etree.fromstring(SUBMODULE_TEMPLATE)
    modulexml.find('Name').attrib['value'] = f'Generated Items Patch ({datetime.datetime.now()})'
    modulexml.find('Id').attrib['value'] = modulename

    dependsnode = modulexml.find('DependedModules')
    for dep in dependencies:
        etree.SubElement(dependsnode, 'DependedModule').attrib['Id'] = dep

    # Write the SubModule.xml
    os.mkdir(outdir)
    etree.ElementTree(modulexml).write(
        os.path.join(outdir, 'SubModule.xml'),
        encoding='utf-8',
        xml_declaration=True,
        pretty_print=True)

    # Write the actual patched items xml
    os.mkdir(os.path.join(outdir, 'ModuleData'))
    etree.ElementTree(itemspatched).write(
        os.path.join(outdir, 'ModuleData', 'patchitems.xml'),
        encoding='utf-8',
        xml_declaration=True,
        pretty_print=True)


def safe_get_node(tree, xpath):
    node = tree.xpath(xpath)
    if len(node) > 0:
        return node[0]
    else:
        return None


class CustomPatcher(object):

    def patch(self, actions, tree):
        # Copy the tree so we don't modify the original
        result = deepcopy(tree)

        for action in actions:
            self.handle_action(action, result)

        return result

    def patch_in_place(self, actions, tree):
        for action in actions:
            self.handle_action(action, tree)
        return tree

    def handle_action(self, action, tree):
        action_type = type(action)
        method = getattr(self, '_handle_' + action_type.__name__)
        method(action, tree)

    def _handle_DeleteNode(self, action, tree):
        node = safe_get_node(tree, action.node)
        if node is not None:
            node.getparent().remove(node)

    def _handle_InsertNode(self, action, tree):
        target = safe_get_node(tree, action.target)
        if target is not None:
            node = target.makeelement(action.tag)
            target.insert(action.position, node)

    def _handle_RenameNode(self, action, tree):
        node = safe_get_node(tree, action.node)
        if node is not None:
            node.tag = action.tag

    def _handle_MoveNode(self, action, tree):
        node = safe_get_node(tree, action.node)
        if node is not None:
            node.getparent().remove(node)
            target = safe_get_node(tree, action.target)
            if target is not None:
                target.insert(action.position, node)

    def _handle_UpdateTextIn(self, action, tree):
        node = safe_get_node(tree, action.node)
        if node is not None:
            node.text = action.text

    def _handle_UpdateTextAfter(self, action, tree):
        node = safe_get_node(tree, action.node)
        if node is not None:
            node.tail = action.text

    def _handle_UpdateAttrib(self, action, tree):
        node = safe_get_node(tree, action.node)
        if node is not None:
            node.attrib[action.name] = action.value

    def _handle_DeleteAttrib(self, action, tree):
        node = safe_get_node(tree, action.node)
        if node is not None and action.name in node.attrib:
            del node.attrib[action.name]

    def _handle_InsertAttrib(self, action, tree):
        node = safe_get_node(tree, action.node)
        if node is not None:
            node.attrib[action.name] = action.value

    def _handle_RenameAttrib(self, action, tree):
        print(f'Renaming attribute is not supported node = {action.node}, attrib old name = {action.oldname}')
        pass
        # node = safe_get_node(tree, action.node)
        # if node is not None:
        #     assert action.oldname in node.attrib
        #     assert action.newname not in node.attrib
        #     node.attrib[action.newname] = node.attrib[action.oldname]
        #     del node.attrib[action.oldname]

    def _handle_InsertComment(self, action, tree):
        target = tree.xpath(action.target)[0]
        target.insert(action.position, etree.Comment(action.text))


if __name__ == "__main__":
    main()
