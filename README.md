# 关于	

## 目前进度

由于我目前有个全职工作的原因，更新将会放缓。如果有想要添加的功能的话请直接提交pull request，或者issue。

感谢理解！

## 需求

* Python版本为 3.10+
* 安装requirements.txt中的所有依赖 `pip install -r requirements.txt`
* 运行Go-CQHTTP[具体文档清参考这里](https://github.com/Mrs4s/go-cqhttp)
* 参考[nonebot](https://github.com/nonebot/nonebot)的配置文档按需在qq_bot_core.py中配置机器人

## 主要功能

* 多种娱乐功能（轮盘赌、明日方舟十连寻访模拟、嘴臭等）
* Twitch切片
* 色图功能！（需要Pixiv账号）
* 搜图功能（支持使用“回复”并直接输入搜图来进行搜图，或者！搜图 [图片]（详见说明文档）
* 权限系统（想要什么群，什么用户使用什么功能均可进行自定义）
* B站监控 + 直播分析
* Discord监控

说明文档在[这里](https://github.com/remiliacn/Lingye-Bot)

### 重要
* 为了更好的使用机器人，请在config.py文件中的`SUPER_USER`参数上设置好自己的QQ号，并使用`添加管理`命令将自己的qq号添加上管理员权限
* 如果在使用机器人的时候遇到了权限问题，请参照[该issue](https://github.com/remiliacn/qqBot/issues/13#issuecomment-1012546963)进行修正


# Config
1. 复制提供的sample_config.py文件，然后改名为config.py
2. 按需填写需要的数据

## go-cqhttp

### config.yml

这个是我目前机器人的配置，仅供参考
```yml
# go-cqhttp 默认配置文件

account: # 账号相关
  uin: 0 # QQ账号
  password: '' # 密码为空时使用扫码登录
  encrypt: false  # 是否开启密码加密
  status: 14      # 在线状态 请参考 https://github.com/Mrs4s/go-cqhttp/blob/dev/docs/config.md#在线状态
  relogin: # 重连设置
    disabled: false
    delay: 3      # 重连延迟, 单位秒
    interval: 0   # 重连间隔
    max-times: 0  # 最大重连次数, 0为无限制

  # 是否使用服务器下发的新地址进行重连
  # 注意, 此设置可能导致在海外服务器上连接情况更差
  use-sso-address: false

heartbeat:
  disabled: true # 是否开启心跳事件上报
  # 心跳频率, 单位秒
  # -1 为关闭心跳
  interval: 5

message:
  # 上报数据类型
  # 可选: string,array
  post-format: string
  # 是否忽略无效的CQ码, 如果为假将原样发送
  ignore-invalid-cqcode: true
  # 是否强制分片发送消息
  # 分片发送将会带来更快的速度
  # 但是兼容性会有些问题
  force-fragment: false
  # 是否将url分片发送
  fix-url: true
  # 下载图片等请求网络代理
  proxy-rewrite: ''
  # 是否上报自身消息
  report-self-message: false
  # 移除服务端的Reply附带的At
  remove-reply-at: false
  # 为Reply附加更多信息
  extra-reply-data: false

output:
  # 日志等级 trace,debug,info,warn,error
  log-level: warn
  # 是否启用 DEBUG
  debug: false # 开启调试模式

# 默认中间件锚点
default-middlewares: &default
  # 访问密钥, 强烈推荐在公网的服务器设置
  access-token: ''
  # 事件过滤器文件目录
  filter: ''
  # API限速设置
  # 该设置为全局生效
  # 原 cqhttp 虽然启用了 rate_limit 后缀, 但是基本没插件适配
  # 目前该限速设置为令牌桶算法, 请参考:
  # https://baike.baidu.com/item/%E4%BB%A4%E7%89%8C%E6%A1%B6%E7%AE%97%E6%B3%95/6597000?fr=aladdin
  rate-limit:
    enabled: false # 是否启用限速
    frequency: 1  # 令牌回复频率, 单位秒
    bucket: 6     # 令牌桶大小

servers:
  # HTTP 通信设置
  - http:
      # 是否关闭正向HTTP服务器
      disabled: false
      # 服务端监听地址
      host: 
      # 服务端监听端口
      port: 5700
      # 反向HTTP超时时间, 单位秒
      # 最小值为5，小于5将会忽略本项设置
      timeout: 360
      middlewares:
        <<: *default # 引用默认中间件
      # 反向HTTP POST地址列表
      post:
      #- url: '' # 地址
      #  secret: ''           # 密钥
      #- url: 127.0.0.1:5701 # 地址
      #  secret: ''          # 密钥

  # 正向WS设置
  - ws:
      # 是否禁用正向WS服务器
      disabled: false
      # 正向WS服务器监听地址
      host: 127.0.0.1
      # 正向WS服务器监听端口
      port: 6700
      middlewares:
        <<: *default # 引用默认中间件

  - ws-reverse:
      # 是否禁用当前反向WS服务
      disabled: false
      # 反向WS Universal 地址
      # 注意 设置了此项地址后下面两项将会被忽略
      universal: 
      # 反向WS API 地址
      api: ws://127.0.0.1:5700/ws/api/
      # 反向WS Event 地址
      event: ws://127.0.0.1:5700/ws/event/
      # 重连间隔 单位毫秒
      reconnect-interval: 3000
      middlewares:
        <<: *default # 引用默认中间件
  # pprof 性能分析服务器, 一般情况下不需要启用.
  # 如果遇到性能问题请上传报告给开发者处理
  # 注意: pprof服务不支持中间件、不支持鉴权. 请不要开放到公网
  - pprof:
      # 是否禁用pprof性能分析服务器
      disabled: true
      # pprof服务器监听地址
      host: 127.0.0.1
      # pprof服务器监听端口
      port: 7700

  # 可添加更多
  #- ws-reverse:
  #- ws:
  #- http:
  #- pprof:

database: # 数据库相关设置
  leveldb:
    # 是否启用内置leveldb数据库
    # 启用将会增加10-20MB的内存占用和一定的磁盘空间
    # 关闭将无法使用 撤回 回复 get_msg 等上下文相关功能
    enable: true
```

如果您没有查询`虚拟货币`
价格，K线以及其技术图形的需求，则可忽略OKEx相关配置。如果您有这方面的需求，请参阅OKEx的[官方API文档](https://www.okex.com/docs/zh/#README)，该链接中有如何获取API KEY， SECRET
KEY，PASSPHRASE和使用OKEx相关API的详细介绍。

在配置后可能会出现部分文件缺失的情况，请按需删除不需要的参数。（因为有些功能是为某些群的需求特供的，所以可能不适合大部分用户）

您可以参考`sample_config`的配置方式对您的机器人进行配置。
