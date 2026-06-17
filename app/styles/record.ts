import { StyleSheet } from 'react-native';

export const styles = StyleSheet.create({
    container: {
      flex: 1,
    },
    content: {
      flex: 1,
      paddingHorizontal: 20,
      paddingBottom: 20,
    },
    statusSection: {
      backgroundColor: '#FBE7E9',
      borderRadius: 16,
      padding: 20,
      marginBottom: 24,
    },
    statusRow: {
      flexDirection: 'row',
      justifyContent: 'center',
      alignItems: 'center',
    },
    statusItem: {
      alignItems: 'center',
      paddingHorizontal: 24,
    },
    statusValue: {
      fontSize: 32,
      fontWeight: '700',
      color: '#1A1C1E',
    },
    statusLabel: {
      fontSize: 14,
      color: '#5F6368',
      marginTop: 4,
    },
    statusDivider: {
      width: 1,
      height: 40,
      backgroundColor: '#E4E7EA',
    },
    recordingIndicator: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      marginTop: 16,
    },
    recordingDot: {
      width: 10,
      height: 10,
      borderRadius: 5,
      backgroundColor: '#D62F3F',
      marginRight: 8,
    },
    recordingText: {
      fontSize: 14,
      fontWeight: '500',
      color: '#D62F3F',
    },
    switchContainer: {
      alignItems: 'center',
      paddingTop: 12,
    },
    animationContainer: {
      flex: 1,
      justifyContent: 'center',
      alignItems: 'center',
    },
    animation: {
      width: '100%',
      height: '100%',
    },

  });
  