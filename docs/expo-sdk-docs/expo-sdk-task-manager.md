# TaskManager

_A library that provides support for tasks that can run in the background._

Available on platforms android, ios, tvos, expo-go

`expo-task-manager` provides an API that allows you to manage long-running tasks, in particular those tasks that can run while your app is in the background. Some features of this library are used by other libraries under the hood. Here is a list of Expo SDK libraries that use `TaskManager`.

## Libraries using Expo TaskManager

- [Location](location.mdx)
- [BackgroundTask](background-task.mdx)
- [BackgroundFetch](background-fetch.mdx)
- [Notifications](notifications.mdx)

## Installation

```bash
$ npx expo install expo-task-manager
```

If you are installing this in an existing React Native app, make sure to install `expo` in your project.

<br />

> **info** You can test `TaskManager` in the Expo Go app. However, check the documentation of each [library](#libraries-using-expo-taskmanager) that uses `TaskManager` to confirm whether it supports testing in Expo Go.

## Configuration&ensp;<PlatformTag platform='ios' />

Standalone apps need some extra configuration: on iOS, each background feature requires a special key in `UIBackgroundModes` array in your **Info.plist** file.

Read more about how to configure this in the reference for each of the [libraries](#libraries-using-expo-taskmanager) that use `TaskManager`.

## Example

```jsx
import React from 'react';
import { Button, View, StyleSheet } from 'react-native';
import * as TaskManager from 'expo-task-manager';
import * as Location from 'expo-location';

const LOCATION_TASK_NAME = 'background-location-task';

const requestPermissions = async () => {
  const { status: foregroundStatus } = await Location.requestForegroundPermissionsAsync();
  if (foregroundStatus === 'granted') {
    const { status: backgroundStatus } = await Location.requestBackgroundPermissionsAsync();
    if (backgroundStatus === 'granted') {
      await Location.startLocationUpdatesAsync(LOCATION_TASK_NAME, {
        accuracy: Location.Accuracy.Balanced,
      });
    }
  }
};

const PermissionsButton = () => (
  <View style={styles.container}>
    <Button onPress={requestPermissions} title="Enable background location" />
  </View>
);

TaskManager.defineTask(LOCATION_TASK_NAME, ({ data, error }) => {
  if (error) {
    // Error occurred - check `error.message` for more details.
    return;
  }
  if (data) {
    const { locations } = data;
    // do something with the locations captured in the background
  }
});

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});

export default PermissionsButton;
```

## API

```js
import * as TaskManager from 'expo-task-manager';
```

## API: expo-task-manager

### TaskManager Methods

#### defineTask (*Function*)
- `defineTask(taskName: string, taskExecutor: TaskManagerTaskExecutor<T>)`
  Defines task function. It must be called in the global scope of your JavaScript bundle.
  In particular, it cannot be called in any of React lifecycle methods like `componentDidMount`.
  This limitation is due to the fact that when the application is launched in the background,
  we need to spin up your JavaScript app, run your task and then shut down — no views are mounted
  in this scenario.
  | Parameter | Type | Description |
  | --- | --- | --- |
  | `taskName` | string | Name of the task. It must be the same as the name you provided when registering the task. |
  | `taskExecutor` | TaskManagerTaskExecutor<T> | A function that will be invoked when the task with given `taskName` is executed. |

#### getRegisteredTasksAsync (*Function*)
- `getRegisteredTasksAsync(): Promise<TaskManagerTask[]>`
  Provides information about tasks registered in the app.
  Returns: A promise which fulfills with an array of tasks registered in the app.
  Example:
  ```js
  [
    {
      taskName: 'location-updates-task-name',
      taskType: 'location',
      options: {
        accuracy: Location.Accuracy.High,
        showsBackgroundLocationIndicator: false,
      },
    },
    {
      taskName: 'geofencing-task-name',
      taskType: 'geofencing',
      options: {
        regions: [...],
      },
    },
  ]
  ```

#### getTaskOptionsAsync (*Function*)
- `getTaskOptionsAsync(taskName: string): Promise<TaskOptions>`
  Retrieves `options` associated with the task, that were passed to the function registering the task
  (e.g. `Location.startLocationUpdatesAsync`).
  | Parameter | Type | Description |
  | --- | --- | --- |
  | `taskName` | string | Name of the task. |
  Returns: A promise which fulfills with the `options` object that was passed while registering task
  with given name or `null` if task couldn't be found.

#### isAvailableAsync (*Function*)
- `isAvailableAsync(): Promise<boolean>`
  Determine if the `TaskManager` API can be used in this app.
  Returns: A promise which fulfills with `true` if the API can be used, and `false` otherwise.
  With Expo Go, `TaskManager` is not available on Android, and does not support background execution on iOS.
  Use a development build to avoid limitations: https://expo.fyi/dev-client.
  On the web, it always returns `false`.

#### isTaskDefined (*Function*)
- `isTaskDefined(taskName: string): boolean`
  Checks whether the task is already defined.
  | Parameter | Type | Description |
  | --- | --- | --- |
  | `taskName` | string | Name of the task. |

#### isTaskRegisteredAsync (*Function*)
- `isTaskRegisteredAsync(taskName: string): Promise<boolean>`
  Determine whether the task is registered. Registered tasks are stored in a persistent storage and
  preserved between sessions.
  | Parameter | Type | Description |
  | --- | --- | --- |
  | `taskName` | string | Name of the task. |
  Returns: A promise which resolves to `true` if a task with the given name is registered, otherwise `false`.

#### unregisterAllTasksAsync (*Function*)
- `unregisterAllTasksAsync(): Promise<void>`
  Unregisters all tasks registered for the running app. You may want to call this when the user is
  signing out and you no longer need to track his location or run any other background tasks.
  Returns: A promise which fulfills as soon as all tasks are completely unregistered.

#### unregisterTaskAsync (*Function*)
- `unregisterTaskAsync(taskName: string): Promise<void>`
  Unregisters task from the app, so the app will not be receiving updates for that task anymore.
  _It is recommended to use methods specialized by modules that registered the task, eg.
  [`Location.stopLocationUpdatesAsync`](./location/#expolocationstoplocationupdatesasynctaskname)._
  | Parameter | Type | Description |
  | --- | --- | --- |
  | `taskName` | string | Name of the task to unregister. |
  Returns: A promise which fulfills as soon as the task is unregistered.

### Interfaces

#### TaskManagerError (*Interface*)
Error object that can be received through [`TaskManagerTaskBody`](#taskmanagertaskbody) when the
task fails.
##### Properties
- `code` (string | number)
- `message` (string)

#### TaskManagerTask (*Interface*)
Represents an already registered task.
##### Properties
- `options` (any)
  Provides `options` that the task was registered with.
- `taskName` (string)
  Name that the task is registered with.
- `taskType` (string)
  Type of the task which depends on how the task was registered.

#### TaskManagerTaskBody (*Interface*)
Represents the object that is passed to the task executor.
##### Properties
- `data` (TaskManagerTaskBody.T)
  An object of data passed to the task executor. Its properties depend on the type of the task.
- `error` (null | TaskManagerError)
  Error object if the task failed or `null` otherwise.
- `executionInfo` (TaskManagerTaskBodyExecutionInfo)
  Additional details containing unique ID of task event and name of the task.

#### TaskManagerTaskBodyExecutionInfo (*Interface*)
Additional details about execution provided in `TaskManagerTaskBody`.
##### Properties
- `appState?` ('active' | 'background' | 'inactive')
  State of the application.
  Available on platform: ios
- `eventId` (string)
  Unique ID of task event.
- `taskName` (string)
  Name of the task.

### Types

#### TaskManagerTaskExecutor (*Type*)
Type of task executor – a function that handles the task.
Type: (body: TaskManagerTaskBody<T>) => Promise<any>