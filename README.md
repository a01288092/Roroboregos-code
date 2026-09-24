# Roroboregos-code

Código del robot **Roroboregos** para competencia de robótica. Sistema integrado de motores a pasos (NEMA 17 + TMC2209), sensor MPU6050, sensor ultrasónico, sensor de color (TCS3200) y LEDs de salida.

## 📋 Características

- ✅ **Control de motor paso a paso** (NEMA 17 con driver TMC2209)
- ✅ **Aceleración y velocidad suave** (librería AccelStepper)
- ✅ **Sensor acelerómetro/giroscopio** (MPU6050) para estabilización
- ✅ **Sensor ultrasónico** (HC-SR04) para detección de distancia
- ✅ **Sensor de color** (TCS3200) para identificación de objetos
- ✅   **Sistema de LEDs** indicadores por color detectado

## 🔧 Hardware Requerido

| Componente | Cantidad | Especificación |
|-----------|----------|----------------|
| Arduino (Mega/Uno) | 1 | - |
| Motor NEMA 17 | 1 | 200 pasos/vuelta |
| Driver Motor | 1 | TMC2209 |
| Sensor Acelerómetro | 1 | MPU6050 |
| Sensor Ultrasónico | 1 | HC-SR04 |
| Sensor Color | 1 | TCS3200 |
| LEDs | 4 | Cian, Amarillo, Naranja, Rosa |
| Resistencias | Varias | 220Ω para LEDs |

## 📌 Conexiones de Pines

### Motor NEMA 17 (TMC2209)
```
STEP  → Pin 3
DIR   → Pin 2
ENABLE → Pin 4
```

### Sensor Ultrasónico (HC-SR04)
```
Trig → Pin 12
Echo → Pin 11
```

### Sensor Color (TCS3200)
```
S0 → Pin 2
S1 → Pin 3
S2 → Pin 4
S3 → Pin 5
Out → Pin 6
```

### LEDs de Salida
```
LED Cian    → Pin 7
LED Amarillo → Pin 8
LED Naranja → Pin 9
LED Rosa    → Pin 10
```

### Sensor MPU6050
```
SDA → Pin 20 (Arduino Mega) o A4 (Arduino Uno)
SCL → Pin 21 (Arduino Mega) o A5 (Arduino Uno)
```

## 📦 Librerías Requeridas

Instala las siguientes librerías desde el Arduino IDE:

```
- AccelStepper (por Mike McCauley)
- Adafruit_MPU6050 (por Adafruit)
- Adafruit_Sensor (por Adafruit)
```

**Instalación:** Arduino IDE → Sketch → Include Library → Manage Libraries → Buscar y instalar

## 🚀 Estructura del Proyecto

```
Roroboregos-code/
├── README.md                  # Este archivo
├── LICENSE                    # Licencia del proyecto
├── .gitignore                 # Archivos a ignorar en Git
├── src/
│   ├── 01_motor_basico.ino       # Control básico motor NEMA 17
│   ├── 02_motor_con_accelstepper.ino  # Motor con aceleración suave
│   ├── 03_motor_con_mpu6050.ino      # Motor + Acelerómetro
│   ├── 04_sensor_ultrasonico.ino     # Detección ultrasónica
│   └── 05_sensor_color_leds.ino      # Sensor color + LEDs
└── docs/
    ├── SETUP.md               # Guía de instalación
    └── CONFIGURACION.md       # Configuración de sensores
```

## 🔨 Instalación y Uso

### 1. Clonar el Repositorio
```bash
git clone https://github.com/a01288092/Roroboregos-code.git
cd Roroboregos-code
```

### 2. Configurar Arduino IDE
- Abre Arduino IDE
- Selecciona tu placa (Tools → Board)
- Selecciona el puerto COM (Tools → Port)
- Instala las librerías requeridas (ver sección Librerías)

### 3. Cargar el Código
- Abre el archivo `.ino` que desees usar desde la carpeta `src/`
- Haz clic en "Subir" (Upload) o presiona `Ctrl+U`

### 4. Monitor Serial
- Abre Tools → Serial Monitor
- Velocidad: **115200 baudios**
- Observa los mensajes de diagnóstico

## 📊 Calibración

### Sensor de Color (TCS3200)
El sensor necesita calibración según tu ambiente:

1. Coloca un objeto blanco frente al sensor
2. Abre el Monitor Serial y anota los valores de **freqR, freqG, freqB**
3. Usa estos valores para actualizar en `05_sensor_color_leds.ino`:

```cpp
int R_Min = XX, R_Max = XX;  // Actualizar con tus valores
int G_Min = XX, G_Max = XX;
int B_Min = XX, B_Max = XX;
```

### Distancia de Detección
Modifica en `05_sensor_color_leds.ino`:

```cpp
const int distanciaDeteccion = 5;  // En centímetros
```

## 🐛 Solución de Problemas

| Problema | Solución |
|----------|----------|
| Motor no se mueve | Verifica conexión ENABLE en LOW |
| MPU6050 no detectado | Revisa conexión I2C (SDA/SCL) |
| Sensor ultrasónico sin lectura | Verifica voltaje (debe ser 5V) |
| LEDs no encienden correctamente | Calibra sensor de color (ver arriba) |

## 📚 Referencias

- [AccelStepper Documentation](http://www.airspayce.com/mikem/arduino/AccelStepper/)
- [Adafruit MPU6050 Guide](https://learn.adafruit.com/mpu6050-6-axis-accelerometer-gyro)
- [TCS3200 Color Sensor](https://www.makerguides.com/tcs3200-color-sensor-arduino-tutorial/)
- [HC-SR04 Ultrasonic Sensor](https://howtomechatronics.com/tutorials/arduino/ultrasonic-sensor-hc-sr04/)

## 👥 Contribuidores

- **Equipo Roroboregos**

## 📄 Licencia

Este proyecto está bajo licencia **MIT**. Ver archivo [LICENSE](LICENSE) para más detalles.

## 📞 Contacto y Soporte

Para reportar problemas, sugerencias o mejoras, abre un [Issue](https://github.com/a01288092/Roroboregos-code/issues) en el repositorio.

---

**Última actualización:** Septiembre 2026  
**Versión:** 1.0
