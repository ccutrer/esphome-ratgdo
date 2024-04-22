import esphome.codegen as cg
import esphome.config_validation as cv
import voluptuous as vol
from esphome.components import uart
from esphome import automation, pins
from esphome.const import CONF_ID, CONF_TRIGGER_ID, CONF_RX_PIN, CONF_TX_PIN, CONF_UART_ID
from esphome.core import CORE
from esphome.cpp_generator import MockObj

DEPENDENCIES = ["preferences", "uart"]
MULTI_CONF = True


ratgdo_ns = cg.esphome_ns.namespace("ratgdo")
RATGDO = ratgdo_ns.class_("RATGDOComponent", cg.Component, uart.UARTDevice)


SyncFailed = ratgdo_ns.class_("SyncFailed", automation.Trigger.template())

# D4 red control terminal / GarageDoorOpener (UART1 TX) pin is D4 on D1 Mini
# D2 red control terminal / GarageDoorOpener (UART1 RX) pin is D2 on D1 Mini
CONF_INPUT_OBST = "input_obst_pin"
DEFAULT_INPUT_OBST = "D7"  # D7 black obstruction sensor terminal

CONF_RATGDO_ID = "ratgdo_id"

CONF_ON_SYNC_FAILED = "on_sync_failed"
CONF_PROTOCOL = "protocol"

PROTOCOL_SECPLUSV1 = "secplusv1"
PROTOCOL_SECPLUSV2 = "secplusv2"
PROTOCOL_DRYCONTACT = "drycontact"
SUPPORTED_PROTOCOLS = [PROTOCOL_SECPLUSV1, PROTOCOL_SECPLUSV2, PROTOCOL_DRYCONTACT]

CONF_UART = "uart"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(RATGDO),
        cv.Optional(CONF_INPUT_OBST, default=DEFAULT_INPUT_OBST): cv.Any(
            cv.none, pins.gpio_input_pin_schema
        ),
        cv.Optional(CONF_ON_SYNC_FAILED): automation.validate_automation(
            {
                cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(SyncFailed),
            }
        ),
        cv.Optional(CONF_PROTOCOL, default=PROTOCOL_SECPLUSV2): vol.In(
            SUPPORTED_PROTOCOLS
        ),
    }
).extend(uart.UART_DEVICE_SCHEMA).extend(cv.COMPONENT_SCHEMA)

FINAL_VALIDATE_SCHEMA = uart.final_validate_device_schema(
    "ratgdo",
    require_tx=True,
    require_rx=True,
    data_bits=8,
    stop_bits=1,
)

RATGDO_CLIENT_SCHMEA = cv.Schema(
    {
        cv.Required(CONF_RATGDO_ID): cv.use_id(RATGDO),
    }
)


async def register_ratgdo_child(var, config):
    parent = await cg.get_variable(config[CONF_RATGDO_ID])
    cg.add(var.set_parent(parent))


def get_uart_config(uart_id):
    uarts = CORE.config.get(CONF_UART, {})
    for uart in uarts:
        if uart.get(CONF_ID, None) == uart_id:
            return uart
    raise cv.Invalid(f"UART id '{uart_id}' not found")

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)
    uart_config = get_uart_config(config[CONF_UART_ID])
    # the pins have already been declared by the UART;
    # we just need to figure out their variable names
    # to pass them directly to our component
    pin_id = uart_config[CONF_TX_PIN][CONF_ID]
    cg.add(var.set_output_gdo_pin(MockObj(pin_id)))
    pin_id = uart_config[CONF_RX_PIN][CONF_ID]
    cg.add(var.set_input_gdo_pin(MockObj(pin_id)))
    if CONF_INPUT_OBST in config and config[CONF_INPUT_OBST]:
        pin = await cg.gpio_pin_expression(config[CONF_INPUT_OBST])
        cg.add(var.set_input_obst_pin(pin))

    for conf in config.get(CONF_ON_SYNC_FAILED, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        await automation.build_automation(trigger, [], conf)

    cg.add_library(
        name="secplus",
        repository="https://github.com/ccutrer/secplus#master",
        version=None,
    )

    if config[CONF_PROTOCOL] == PROTOCOL_SECPLUSV1:
        cg.add_define("PROTOCOL_SECPLUSV1")
    elif config[CONF_PROTOCOL] == PROTOCOL_SECPLUSV2:
        cg.add_define("PROTOCOL_SECPLUSV2")
    elif config[CONF_PROTOCOL] == PROTOCOL_DRYCONTACT:
        cg.add_define("PROTOCOL_DRYCONTACT")
    cg.add(var.init_protocol())
