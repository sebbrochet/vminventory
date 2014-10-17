#!/usr/bin/env python
# -*- coding: utf-8 -*-

import atexit
from pyVim import connect
from pyVmomi import vim, vmodl
import time

import requests
requests.packages.urllib3.disable_warnings()

def myprint(unicodeobj):
    import sys
    print unicodeobj.encode(sys.stdout.encoding or 'utf-8')

def get_full_name(vm):
    current = vm
    full_name = vm.name

    while hasattr(current, 'parentVApp') and current.parentVApp:
        full_name = "%s/%s" % (current.parentVApp.name, full_name)
        current = current.parentVApp

    while hasattr(current, 'parent') and current.parent:
        full_name = "%s/%s" % (current.parent.name, full_name)
        current = current.parent

    return full_name


def get_service_instance(args):
    service_instance = None

    try:
        service_instance = connect.SmartConnect(host=args.target,
                                                user=args.user,
                                                pwd=args.password,
                                                port=int(args.port))
        atexit.register(connect.Disconnect, service_instance)
    except IOError as e:
        pass
    except vim.fault.InvalidLogin, e:
        raise SystemExit("Error: %s" % e.msg)
    except TypeError, e:
        raise SystemExit("Error: %s" % e.message) 

    if not service_instance:
        raise SystemExit("Error: unable to connect to target with supplied info.")

    return service_instance


def get_vm_from_scope_IFN(scope):
    if not scope:
        return None

    vms_from_scope = []

    f = file(scope, "r")
    lines = f.read().split('\n')
    for line in lines:
        if line.startswith('#'):
            continue
        value = line.strip()

	if value:
            vms_from_scope.append(value)

    return vms_from_scope


def is_in_datacenter(vm, datacenter_name):
    return datacenter_name == '' or get_full_name(vm).split('/')[1] == datacenter_name


def is_in_scope(vm, vms_from_scope):
    return vms_from_scope is None or vm.name in vms_from_scope


def get_all_vmx_data(target, service_instance, vms_from_scope, datacenter_name):
    def get_vmx_in_datastore(dsbrowser, dsname, datacenter, fulldsname):
        search = vim.HostDatastoreBrowserSearchSpec()
        search.matchPattern = "*.vmx"
        searchDS = dsbrowser.SearchDatastoreSubFolders_Task(dsname, search)
   
        while searchDS.info.state != "success":
            import time
            time.sleep(0.1)
  
        vmx_data_in_datastore = []

        for rs in searchDS.info.result:
            dsfolder = rs.folderPath
            for f in rs.file:
                try:
                    dsfile = f.path
                    vmfold = dsfolder.split("]")
                    vmfold = vmfold[1]
                    vmfold = vmfold[1:]
                    vmx_data_in_datastore.append((target, vmfold, dsfile, datacenter, fulldsname))
                except Exception, e:
                    print "Caught exception : " + str(e)
                    return []

        return vmx_data_in_datastore 

    all_vmx_data = []

    content = service_instance.RetrieveContent()
    for datacenter in content.rootFolder.childEntity:
        if datacenter_name == '' or datacenter.name == datacenter_name:
            for ds in datacenter.datastore:
                all_vmx_data.extend(get_vmx_in_datastore(ds.browser, "[%s]" % ds.summary.name, datacenter.name, ds.summary.name))

    return all_vmx_data

def get_all_uuid_from_vmx_data(args, all_vmx_data):

    import urllib2, urlparse, base64

    def get_uuid_from_vmx_data(args, vmx_data):
        def url_fix(s, charset='utf-8'):
            if isinstance(s, unicode):
                s = s.encode(charset, 'ignore')
            scheme, netloc, path, qs, anchor = urlparse.urlsplit(s)
            path = urllib2.quote(path, '/%')
            qs = urllib2.quote(qs, ':&=')

            return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))

        username = args.user
        password = args.password

        target, vmfold, dsfile, datacenter, fulldsname = vmx_data
        vmx_url = "https://%s/folder/%s%s?dcPath=%s&dsName=%s" % (target, vmfold, dsfile, datacenter, fulldsname) 
        request = urllib2.Request(url_fix(vmx_url))
        base64string = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        try:
            result = urllib2.urlopen(request)
            vmx_file_lines = result.readlines()
    
            for line in vmx_file_lines:
                if line.startswith("displayName"):
                    dn = line
                elif line.startswith("vc.uuid"):
                    vcid = line

            uuid = vcid.replace('"', "")
            uuid = uuid.replace("vc.uuid = ", "")
            uuid = uuid.strip("\n")
            uuid = uuid.replace(" ", "")
            uuid = uuid.replace("-", "")
            newDN = dn.replace('"', "")
            newDN = newDN.replace("displayName = ", "")
            newDN = newDN.strip("\n")
        
            dspath = "%s/%s" % (fulldsname, vmfold)
            tempdsVM = [newDN, dspath]

        except urllib2.HTTPError, e:
            print "Exception while checking %s:\n%s" % (vmx_url, e)
            return None, "", ""

        return uuid, newDN, dspath

    uuid_from_vmx_data_dict = {}

    for vmx_data in all_vmx_data:
       uuid, datastore_vm, datastore_path = get_uuid_from_vmx_data(args, vmx_data)
       if uuid:
           uuid_from_vmx_data_dict[uuid] = (datastore_vm, datastore_path) 
    
    return uuid_from_vmx_data_dict


def get_all_uuid_from_vm(service_instance):
    uuid_from_vm_dict = {}

    content = service_instance.RetrieveContent()
    object_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)

    for vm in object_view.view:
        uuid = vm.config.instanceUuid
        uuid = uuid.replace("-", "")
        uuid_from_vm_dict[uuid] = vm.name 

    return uuid_from_vm_dict


def get_vmx_data_not_in_inventory(args):
    vmx_data_not_in_inventory = []

    service_instance = get_service_instance(args)
    vms_from_scope = get_vm_from_scope_IFN(args.scope)

    all_vmx_data = get_all_vmx_data(args.target, service_instance, vms_from_scope, args.datacenter)
    uuid_from_vmx_data_dict = get_all_uuid_from_vmx_data(args, all_vmx_data)
    uuid_from_vm_dict = get_all_uuid_from_vm(service_instance)

    uuid_from_vmx_data_set = set(uuid_from_vmx_data_dict.keys())
    uuid_from_vm_set = set(uuid_from_vm_dict.keys())

    missing_uuid_in_vm = uuid_from_vmx_data_set - uuid_from_vm_set

    for uuid in missing_uuid_in_vm:
        vmx_data_not_in_inventory.append(uuid_from_vmx_data_dict[uuid])

    return vmx_data_not_in_inventory
    
def cmd_list_orphaned_vm(args):
    vmx_data_not_in_inventory = get_vmx_data_not_in_inventory(args)

    if vmx_data_not_in_inventory:
        print "Orphaned VM found (Display name - Datastore/Folder name)"
        for datastore_vm, datastore_path in vmx_data_not_in_inventory:
            print "%s - %s" % (datastore_vm, datastore_path)
    else:
        print "No orphaned VM found."


def cmd_add_to_inventory(args):
    vmx_data_not_in_inventory = get_vmx_data_not_in_inventory(args)

    if vmx_data_not_in_inventory:
        for datastore_vm, datastore_path in vmx_data_not_in_inventory:
            folder = get_datastore_folder(datastore_vm, datastore_path)
            if folder:
                folder.RegisterVM(path=datastore_path, asTemplate = False)
    else:
        print "No vmx files to add in inventory."     
