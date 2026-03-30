# Sensors

_A library that provides access to a device's accelerometer, barometer, motion, gyroscope, light, magnetometer, and pedometer._

Available on platforms android, ios, web, expo-go

`expo-sensors` provide various APIs for accessing device sensors to measure motion, orientation, pressure, magnetic fields, ambient light, and step count.

## Installation

```bash
$ npx expo install expo-sensors
```

If you are installing this in an existing React Native app, make sure to install `expo` in your project.

## Configuration in app config

You can configure `expo-sensors` using its built-in [config plugin](https://docs.expo.dev/config-plugins/introduction/) if you use config plugins in your project ([Continuous Native Generation (CNG)](https://docs.expo.dev/workflow/continuous-native-generation/)). The plugin allows you to configure various properties that cannot be set at runtime and require building a new app binary to take effect. If your app does **not** use CNG, then you'll need to manually configure the library.

```json app.json
{
  "expo": {
    "plugins": [
      [
        "expo-sensors",
        {
          "motionPermission": "Allow $(PRODUCT_NAME) to access your device motion"
        }
      ]
    ]
  }
}
```

### Configurable properties
| Name | Default | Description |
| --- | --- | --- |
| `motionPermission` | `"Allow $(PRODUCT_NAME) to access your device motion"` | Only for: ios. A string to set the [`NSMotionUsageDescription`](#permission-nsmotionusagedescription) permission message or `false` to disable motion permissions. |

## API

```js
import * as Sensors from 'expo-sensors';
// OR
import {
  Accelerometer,
  Barometer,
  DeviceMotion,
  Gyroscope,
  LightSensor,
  Magnetometer,
  MagnetometerUncalibrated,
  Pedometer,
} from 'expo-sensors';
```

## Permissions

### Android

Starting in Android 12 (API level 31), the system has a 200Hz limit for each sensor updates.

If you need an update interval greater than 200Hz, you must add the following permissions to your **app.json** inside the [`expo.android.permissions`](../config/app/#permissions) array.

<AndroidPermissions permissions={['HIGH_SAMPLING_RATE_SENSORS']} />

<ConfigReactNative>

If you're not using Continuous Native Generation ([CNG](https://docs.expo.dev/workflow/continuous-native-generation/)) or you're using native **android** project manually, add `HIGH_SAMPLING_RATE_SENSORS` permission to your project's **android/app/src/main/AndroidManifest.xml**:

```xml
<uses-permission android:name="android.permission.HIGH_SAMPLING_RATE_SENSORS" />
```

</ConfigReactNative>

### iOS

The following usage description keys are used by this library:

<IOSPermissions permissions={['NSMotionUsageDescription']} />

## Available sensors

For more information, see the documentation for the sensor you are interested in:

[Accelerometer](https://docs.expo.devaccelerometer)

[Barometer](https://docs.expo.devbarometer)

[DeviceMotion](https://docs.expo.devdevicemotion)

[Gyroscope](https://docs.expo.devgyroscope)

[Magnetometer](https://docs.expo.devmagnetometer)

[LightSensor](https://docs.expo.devlight-sensor)

[Pedometer](https://docs.expo.devpedometer)