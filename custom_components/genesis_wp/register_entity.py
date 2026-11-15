"""Static frontend anchor shared by register entities."""
from genesis_wp.const import KEY_ADDRESS, KEY_REG_TYPE, REGISTERS


# DHF-REQ: genesis-wp-ha/requirement-18
class RegisterAnchor:
    """Expose the library's register identity without recording static metadata."""

    _unrecorded_attributes = frozenset({"register"})

    @property
    def capability_attributes(self):
        """Keep the anchor present even while HA omits unavailable state attributes."""
        spec = REGISTERS[self.kind]
        return {**(super().capability_attributes or {}), "register": f"{spec[KEY_REG_TYPE]}_{spec[KEY_ADDRESS]}"}
