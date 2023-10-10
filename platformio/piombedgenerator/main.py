# from copy import deepcopy, copy
from os import listdir
from os.path import basename, isdir, join
import os

import json
from sys import exit as sys_exit
from string import Template

import sys
sys.path.insert(0, '..')

import tools.build_api
from tools.export import EXPORTERS
from tools.settings import ROOT
from tools.targets import TARGET_MAP
from tools.resources import Resources
from tools.notifier.mock import MockNotifier


MBED_CORE_DIRS = (
    join(ROOT, "cmsis"),
    join(ROOT, "drivers"),
    join(ROOT, "hal"),
    join(ROOT, "platform"),
    join(ROOT, "targets")
)

MBED_COMPONENT_DIRS = (
    join(ROOT, "components", "802.15.4_RF", "atmel-rf-driver"),
    join(ROOT, "components", "802.15.4_RF", "mcr20a-rf-driver"),
    join(ROOT, "components", "storage", "blockdevice", "COMPONENT_DATAFLASH"),
    join(ROOT, "components", "storage", "blockdevice", "COMPONENT_FLASHIAP"),
    join(ROOT, "components", "storage", "blockdevice", "COMPONENT_SD"),
    join(ROOT, "components", "storage", "blockdevice", "COMPONENT_SPIF"),
    join(ROOT, "components", "wifi", "esp8266-driver")
)

MBED_FEATURE_DIRS = (
    join(ROOT, "features", "cryptocell", "FEATURE_CRYPTOCELL310"),
    join(ROOT, "features", "FEATURE_BLE"),
    join(ROOT, "features", "storage", "FEATURE_STORAGE")
)

MBED_FRAMEWORK_DIRS = (
    join(ROOT, "features", "frameworks", "greentea-client"),
    join(ROOT, "features", "frameworks", "mbed-client-cli"),
    join(ROOT, "features", "frameworks", "mbed-client-randlib"),
    join(ROOT, "features", "frameworks", "mbed-coap"),
    join(ROOT, "features", "frameworks", "mbed-trace"),
    join(ROOT, "features", "frameworks", "nanostack-libservice"),
    join(ROOT, "features", "frameworks", "nanostack-libservice")
)

MBED_LIB_DIRS = (
    join(ROOT, "rtos"),
    join(ROOT, "events"),
    join(ROOT, "features", "cellular"),
    join(ROOT, "features", "device_key"),
    join(ROOT, "features", "lorawan"),
    join(ROOT, "features", "lwipstack"),
    join(ROOT, "features", "mbedtls"),
    join(ROOT, "features", "nanostack", "coap-service"),
    join(ROOT, "features", "nanostack", "mbed-mesh-api"),
    join(ROOT, "features", "nanostack", "nanostack-hal-mbed-cmsis-rtos"),
    join(ROOT, "features", "nanostack", "nanostack-interface"),
    join(ROOT, "features", "nanostack", "sal-stack-nanostack"),
    join(ROOT, "features", "nanostack", "sal-stack-nanostack-eventloop"),
    join(ROOT, "features", "nanostack", "targets"),
    join(ROOT, "features", "netsocket"),
    join(ROOT, "features", "nfc"),
    join(ROOT, "features", "storage", "blockdevice"),
    join(ROOT, "features", "storage", "filesystem"),
    join(ROOT, "features", "storage", "nvstore"),
    join(ROOT, "features", "storage", "system_storage"),
    join(ROOT, "features", "unsupported", "dsp"),
    join(ROOT, "features", "unsupported", "rpc"),
    join(ROOT, "features", "unsupported", "USBDevice"),
    join(ROOT, "features", "unsupported", "USBHost")
)


MBED_FRAMEWORK_EXTENSIONS = {
    "components": MBED_COMPONENT_DIRS,
    "features": MBED_FEATURE_DIRS,
    "frameworks": MBED_FRAMEWORK_DIRS,
    "libs": MBED_LIB_DIRS
}


def log_message(msg):
    print msg


def get_resources(paths, toolchain, exclude_dirs=[]):
    res = Resources(MockNotifier())

    for d in exclude_dirs:
        res.ignore_dir(d)

    try:
        res.scan_with_toolchain(paths, toolchain, exclude=False)
    except Exception as e:
        print "Target error: %s" % e
        return None

    return res


def fix_paths(base_path, paths):
    if not paths:
        return []

    base_path = base_path.replace("\\", "/")
    if isinstance(paths, list):
        result = []
        for path in paths:
            path = join(ROOT, path).replace("\\", "/")
            if base_path not in path:
                continue
            fixed = path.replace(base_path, "")[1:]
            if "test" in fixed.lower():
                continue
            result.append(fixed if fixed != "" else ".")
    else:
        paths = paths.replace("\\", "/")
        result = paths.replace(base_path, "")
        if result.startswith('/'):
            result = result[1:]
        if result == "":
            result = "."

    return result


def merge_macro(macro):
    result = ""
    if isinstance(macro, tools.config.ConfigMacro):
        if macro.macro_value:
            result = macro.macro_name + " " + str(macro.macro_value)
        else:
            result = macro.macro_name
    elif macro.value is not None:
        result = macro.macro_name + " " + str(macro.value)
    # else:
    #     result = macro.macro_name

    return result


def get_config_data(target, path, exclude_paths=[]):
    config_toolchain = tools.build_api.prepare_toolchain(
        [path], "", target, "GCC_ARM", silent=True)

    config_resources = get_resources([path], config_toolchain, exclude_paths)
    config_toolchain.config.load_resources(config_resources)
    return config_toolchain.config.get_config_data()


def create_target_dir(target):
    target_dir = join(ROOT, "platformio", "variants", target)
    if not isdir(target_dir):
        os.makedirs(target_dir)


def save_config(target, data):
    config_dir = join(ROOT, "platformio", "variants", target)
    if not isdir(config_dir):
        os.makedirs(config_dir)
    """ Saves dict with configuration for specified board to json file"""
    with open(join(config_dir, target + ".json"), 'w') as config_file:
        json.dump(data, config_file, sort_keys=True, indent=4)


def get_ldscript(resources):
    if resources.linker_script:
        return resources.linker_script.replace(ROOT, "").replace("\\", "/")


def get_softdevice(toolchain, resources):
    softdevice_hex = ""
    try:
        softdevice_hex = fix_paths(ROOT, resources.hex_files)[0]
    except:
        pass

    # try:
    #     softdevice_hex = toolchain.target.EXPECTED_SOFTDEVICES_WITH_OFFSETS[
    #         0]['name']
    # except:
    #     pass

    return softdevice_hex


def get_bootloader(toolchain):
    bootloader_hex = None

    try:
        bootloader_hex = toolchain.target.EXPECTED_SOFTDEVICES_WITH_OFFSETS[
            0]['boot']
    except:
        pass

    return bootloader_hex


def get_toolchain_flags(profile, toolchain="GCC_ARM"):
    if profile not in ("release", "debug", "develop"):
        print "Unknown toolchain profile"

    with open(join(ROOT, "tools", "profiles", "%s.json" % profile)) as fp:
        toolchain_configs = json.load(fp)

    return toolchain_configs.get(toolchain, dict())


def extract_component_parameters(base_path, resources):
    
    parameters = {
        "inc_dirs": fix_paths(base_path, resources.inc_dirs),
        "s_sources": fix_paths(base_path, resources.s_sources),
        "c_sources": fix_paths(base_path, resources.c_sources),
        "cpp_sources": fix_paths(base_path, resources.cpp_sources),
        "libraries": fix_paths(base_path, resources.libraries)
    }

    return parameters


def create_config_include(target, config_data):
    TMPL = """
// Automatically generated configuration file.

# ifndef __MBED_CONFIG_DATA__
# define __MBED_CONFIG_DATA__

// Configuration parameters

$config_str

# endif
"""
    symbols = list()
    for config in config_data:
        for _, val in config.items():
            # From 5.9.X version Nordic targets require SOFTDEVICE_PRESENT flag
            if "SOFTDEVICE" in val.macro_name or "PRESENT" not in val.macro_name:
                macro = merge_macro(val)
                if macro:
                    symbols.append(macro)

    data = ""
    for symbol in symbols:
        data += "#if !defined(%s)\n" % symbol.split(" ")[0]
        data += "\t#define " + symbol + "\n"
        data += "#endif\n"

    config = Template(TMPL)
    config_file = join(ROOT, "platformio", "variants",
                       target, "mbed_config.h")

    with open(config_file, "w") as fp:
        fp.write(config.substitute(config_str=data))


def process_memory_regions(toolchain):
    # Some targets need additional info about memory structure
    # see tools/toolchains/__init__.py -> mbedToolchain.add_regions
    regions = []
    try:
        regions = list(toolchain.config.regions)
    except:
        return

    for region in regions:
        for define in [(region.name.upper() + "_ADDR", region.start),
                       (region.name.upper() + "_SIZE", region.size)]:
            define_string = "-D%s=0x%x" % define
            toolchain.cc.append(define_string)
            toolchain.cppc.append(define_string)
            toolchain.flags["common"].append(define_string)
        if region.active:
            for define in [("MBED_APP_START", region.start),
                           ("MBED_APP_SIZE", region.size)]:
                define_string = toolchain.make_ld_define(*define)
                toolchain.ld.append(define_string)
                toolchain.flags["ld"].append(define_string)


def get_component_parameters(component_path, target):
    component_params = dict()
    component_toolchain = tools.build_api.prepare_toolchain(
        [component_path], "", target, "GCC_ARM")

    component_resources = get_resources([component_path], component_toolchain)
    if not component_resources:
        print "Warning! Empty resource list ..."
        return {}, ()

    component_params = extract_component_parameters(
        component_path, component_resources)
    component_params['dir'] = fix_paths(
        ROOT, component_path)

    component_config_data = component_toolchain.config.get_config_data()

    return component_params, component_config_data


def process_mbed_core(target):
    core_toolchain = tools.build_api.prepare_toolchain(
        [ROOT], "", target, "GCC_ARM")

    core_resources = get_resources(MBED_CORE_DIRS, core_toolchain)
    if not core_resources:
        print "Target %s is not supported" % target
        return {}, ()

    mbed_params = {
        "symbols": core_toolchain.get_symbols(),
        "build_flags": core_toolchain.flags,
        "syslibs": core_toolchain.sys_libs,
        "ldscript": get_ldscript(core_resources),
        "softdevice_hex": get_softdevice(core_toolchain, core_resources)
    }

    # add default toolchain flags
    for key, value in get_toolchain_flags("release").iteritems():
        mbed_params['build_flags'][key].extend(value)

    mbed_params['core'] = extract_component_parameters(ROOT, core_resources)
    core_config_data = core_toolchain.config.get_config_data()

    return mbed_params, core_config_data


def main():

    log_message("Targets count %d" % len(EXPORTERS['make_gcc_arm'].TARGETS))
    exporter = EXPORTERS['make_gcc_arm']
    for target in TARGET_MAP:
        if "VBLUNO51" in target:
            print "Skipping VBLUNO51_BOOT"
            continue

        if not exporter.is_target_supported(target) and "mts" not in target.lower():
            log_message("* Skipped target %s" % target)
            continue

        log_message("Current target %s" % target)
        create_target_dir(target)

        framework_configs = []

        mbed_parameters, core_configs = process_mbed_core(target)
        framework_configs.extend(core_configs)

        for component, dirs in MBED_FRAMEWORK_EXTENSIONS.items():
            component_params = dict()
            for component_dir in dirs:
                params, config_data = get_component_parameters(
                    component_dir, target)
                framework_configs.extend(config_data)
                component_params[basename(component_dir)] = params

            mbed_parameters[component] = component_params

        # Add include with configuration file
        create_config_include(target, framework_configs)

        mbed_parameters['build_flags']['common'].extend(
            ["-include", "mbed_config.h"]
        )

        save_config(target, mbed_parameters)

if __name__ == "__main__":
    sys_exit(main())
