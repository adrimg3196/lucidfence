#!/usr/bin/env lua
-- document_loader.lua — carga y muestra archivos de texto
-- Uso: lua document_loader.lua /ruta/al/archivo
-- Si no hay argumentos, pide el archivo interactivamente

local path = arg and arg[1] or nil

if not path or path == "" then
  io.write("Path al archivo: ")
  io.flush()
  path = io.read("*l")
  if not path then
    io.stderr:write("No se proporcionó ruta.\n")
    os.exit(1)
  end
  path = path:gsub("^%s+", ""):gsub("%s+$", "")
  if path == "" then
    io.stderr:write("No se proporcionó ruta.\n")
    os.exit(1)
  end
end

local file, err = io.open(path, "r")
if not file then
  io.stderr:write(string.format("Error al abrir '%s': %s\n", path, err or "archivo no encontrado"))
  os.exit(1)
end

local content = file:read("*a")
file:close()

if not content then
  io.stderr:write("Error: archivo vacío o error de lectura.\n")
  os.exit(1)
end

io.write(content)
