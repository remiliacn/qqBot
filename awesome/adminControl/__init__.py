from .group_control import GroupControlModule
from .setu import SetuFunctionControl
from .user_control import UserControl

user_control = UserControl()
setu_function_control = SetuFunctionControl()
group_control = GroupControlModule()

get_privilege = lambda x, y: user_control.get_user_privilege(x, y)
