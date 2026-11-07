terraform {
  required_version = ">= 1.17.0, < 2.0"
  required_providers {
    vmworkstation = {
      source  = "elsudano/vmworkstation"
      version = "2.0.1"
    }
  }
}

provider "vmworkstation" {
  endpoint = var.vmrest_endpoint
  username = var.vmrest_username
  password = var.vmrest_password
  https    = false
  debug    = "NONE"
}

data "vmworkstation_virtual_machine" "base" {
  denomination = var.base_name
}

resource "vmworkstation_virtual_machine" "node" {
  for_each     = var.nodes
  sourceid     = data.vmworkstation_virtual_machine.base.id
  denomination = "spacecube-${each.key}"
  description  = data.vmworkstation_virtual_machine.base.description
  path         = "${var.vm_root_win}\\spacecube-${each.key}\\spacecube-${each.key}.vmx"
  processors   = each.value.cpu
  memory       = each.value.memory
  state        = var.power_state
}

resource "terraform_data" "seed" {
  for_each         = var.nodes
  triggers_replace = [vmworkstation_virtual_machine.node[each.key].id]
  provisioner "local-exec" {
    command = "python3 prepare_guest.py"
    environment = {
      VMX_WIN = vmworkstation_virtual_machine.node[each.key].path
      VM_ID   = vmworkstation_virtual_machine.node[each.key].id
      VM_ROLE = each.key
      VM_IP   = each.value.ip
    }
  }
}

output "nodes" {
  value = { for role, vm in vmworkstation_virtual_machine.node : role => {
    id = vm.id, path = vm.path, ip = var.nodes[role].ip
  } }
}
