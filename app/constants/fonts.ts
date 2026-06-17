/**
 * App-wide typography: Inter (clean grotesk, SBB-style legibility).
 *
 * NativeWind compiles every `className` into a `style` prop, so the usual
 * `Text.defaultProps` trick can't add a default font (the element-level style
 * always wins). Instead we patch `Text`/`TextInput` render to append the Inter
 * family that matches each element's `fontWeight`. This is safe: it calls the
 * original render and only *adds* a `fontFamily`, so the worst case is the font
 * not applying — never a render failure.
 */

import React from 'react';
import { StyleSheet, Text, TextInput } from 'react-native';
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
} from '@expo-google-fonts/inter';

export const interFontMap = {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
};

const WEIGHT_TO_FAMILY: Record<string, string> = {
  '100': 'Inter_400Regular',
  '200': 'Inter_400Regular',
  '300': 'Inter_400Regular',
  '400': 'Inter_400Regular',
  normal: 'Inter_400Regular',
  '500': 'Inter_500Medium',
  '600': 'Inter_600SemiBold',
  '700': 'Inter_700Bold',
  bold: 'Inter_700Bold',
  '800': 'Inter_700Bold',
  '900': 'Inter_700Bold',
};

let applied = false;

export function applyInterFont(): void {
  if (applied) return;
  applied = true;
  for (const Comp of [Text, TextInput] as any[]) {
    const original = Comp.render;
    if (typeof original !== 'function') continue;
    Comp.render = function patchedRender(...args: any[]) {
      const element = original.apply(this, args);
      if (!element || !element.props) return element;
      const flat = StyleSheet.flatten(element.props.style) || {};
      const family =
        flat.fontFamily ||
        WEIGHT_TO_FAMILY[String(flat.fontWeight ?? '400')] ||
        'Inter_400Regular';
      return React.cloneElement(element, {
        style: [element.props.style, { fontFamily: family }],
      });
    };
  }
}
