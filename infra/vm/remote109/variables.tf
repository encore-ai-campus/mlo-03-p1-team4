variable "vmrest_endpoint" { type = string }
variable "vmrest_username" { type = string }
variable "vmrest_password" {
  type      = string
  sensitive = true
}
variable "base_name" { type = string }
variable "vm_root_win" { type = string }
variable "power_state" {
  type    = string
  default = "off"
  validation {
    condition     = contains(["on", "off"], var.power_state)
    error_message = "전원은 on 또는 off만 허용합니다."
  }
}
variable "nodes" {
  type = map(object({ ip = string, cpu = number, memory = number }))
  default = {
    gw   = { ip = "192.168.0.218", cpu = 1, memory = 768 }
    api1 = { ip = "192.168.0.214", cpu = 1, memory = 1536 }
    api2 = { ip = "192.168.0.215", cpu = 1, memory = 1536 }
    mon  = { ip = "192.168.0.217", cpu = 2, memory = 3072 }
  }
  validation {
    condition     = toset(keys(var.nodes)) == toset(["gw", "api1", "api2", "mon"])
    error_message = "새 시스템의 gw/api1/api2/mon 4대만 관리합니다."
  }
}
