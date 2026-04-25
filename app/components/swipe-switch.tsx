/**
 * SwipeSwitch - A swipeable toggle switch for starting/stopping recording.
 * 
 * Swipe right to turn ON, swipe left to turn OFF.
 */
import React from 'react';
import { StyleSheet, View, Text } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { Ionicons } from '@expo/vector-icons';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  runOnJS,
  interpolate,
  interpolateColor,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

interface SwipeSwitchProps {
  value: boolean;
  onValueChange: (value: boolean) => void;
  disabled?: boolean;
  onLabel?: string;
  offLabel?: string;
  testID?: string;
}

const BRAND_BLUE = '#009DFF';
const TRACK_WIDTH = 340;
const TRACK_HEIGHT = 76;
const THUMB_SIZE = 64;
const THUMB_MARGIN = 4;
const MAX_TRANSLATE = TRACK_WIDTH - THUMB_SIZE - THUMB_MARGIN * 2;

export function SwipeSwitch({
  value,
  onValueChange,
  disabled = false,
  onLabel = 'Recording',
  offLabel = 'Swipe to Record',
  testID,
}: SwipeSwitchProps) {
  const translateX = useSharedValue(value ? MAX_TRANSLATE : 0);
  const startX = useSharedValue(0);

  const triggerHaptic = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  };

  const handleValueChange = (newValue: boolean) => {
    if (newValue !== value) {
      onValueChange(newValue);
    }
  };

  const panGesture = Gesture.Pan()
    .enabled(!disabled)
    .onStart(() => {
      startX.value = translateX.value;
    })
    .onUpdate((event) => {
      const newX = startX.value + event.translationX;
      translateX.value = Math.max(0, Math.min(MAX_TRANSLATE, newX));
    })
    .onEnd((event) => {
      const velocity = event.velocityX;
      const currentX = translateX.value;
      
      // Determine final state based on position and velocity
      let shouldBeOn: boolean;
      
      if (Math.abs(velocity) > 500) {
        // Fast swipe - use velocity direction
        shouldBeOn = velocity > 0;
      } else {
        // Slow swipe - use position threshold (past halfway)
        shouldBeOn = currentX > MAX_TRANSLATE / 2;
      }

      const targetX = shouldBeOn ? MAX_TRANSLATE : 0;
      translateX.value = withSpring(targetX, {
        damping: 20,
        stiffness: 300,
      });

      if (shouldBeOn !== value) {
        runOnJS(triggerHaptic)();
        runOnJS(handleValueChange)(shouldBeOn);
      }
    });

  const thumbAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  const trackAnimatedStyle = useAnimatedStyle(() => {
    const progress = translateX.value / MAX_TRANSLATE;
    return {
      backgroundColor: interpolateColor(progress, [0, 1], ['#FFFFFF', '#E6F7FF']),
      borderColor: BRAND_BLUE,
    };
  });

  const labelAnimatedStyle = useAnimatedStyle(() => {
    const progress = translateX.value / MAX_TRANSLATE;
    return {
      opacity: interpolate(progress, [0, 0.3, 0.7, 1], [1, 0, 0, 1]),
    };
  });

  const labelTextAnimatedStyle = useAnimatedStyle(() => {
    const progress = translateX.value / MAX_TRANSLATE;
    return {
      color: interpolateColor(progress, [0, 1], [BRAND_BLUE, BRAND_BLUE]),
    };
  });

  // Sync with external value changes
  React.useEffect(() => {
    translateX.value = withSpring(value ? MAX_TRANSLATE : 0, {
      damping: 20,
      stiffness: 300,
    });
  }, [value]);

  return (
    <View testID={testID} style={[styles.container, disabled && styles.disabled]}>
      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.track, trackAnimatedStyle]}>
          <Animated.View style={[styles.labelContainer, labelAnimatedStyle]}>
            <Animated.Text style={[styles.label, labelTextAnimatedStyle]}>
              {value ? onLabel : offLabel}
            </Animated.Text>
          </Animated.View>
          
          <Animated.View style={[styles.thumb, thumbAnimatedStyle]}>
            <Ionicons
              name={value ? 'stop' : 'chevron-forward'}
              size={26}
              color="#FFFFFF"
              style={styles.thumbIcon}
            />
          </Animated.View>
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  disabled: {
    opacity: 0.5,
  },
  track: {
    width: TRACK_WIDTH,
    height: TRACK_HEIGHT,
    borderRadius: TRACK_HEIGHT / 2,
    justifyContent: 'center',
    paddingHorizontal: THUMB_MARGIN,
    borderWidth: 3,
  },
  labelContainer: {
    position: 'absolute',
    left: 0,
    right: 0,
    alignItems: 'center',
  },
  label: {
    fontSize: 18,
    fontWeight: '700',
  },
  thumb: {
    width: THUMB_SIZE,
    height: THUMB_SIZE,
    borderRadius: THUMB_SIZE / 2,
    backgroundColor: BRAND_BLUE,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.16,
    shadowRadius: 4,
    elevation: 4,
    justifyContent: 'center',
    alignItems: 'center',
  },
  thumbIcon: {
    marginLeft: 2,
  },
});

export default SwipeSwitch;
