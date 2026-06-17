__all__ = ["ZteC300V125P3TelnetDriver"]


def __getattr__(name: str):
    if name == "ZteC300V125P3TelnetDriver":
        from app.drivers.zte.c300_v125p3_telnet.driver import ZteC300V125P3TelnetDriver

        return ZteC300V125P3TelnetDriver
    raise AttributeError(name)
