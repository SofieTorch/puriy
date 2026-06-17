import { StyleSheet } from "react-native";

const HEADER_BLUE = '#3D6CB4';
const HEADER_BLUE_DARK = '#2F5690';
const SEGMENT_ACTIVE_BORDER_COLOR = '#1E3A66';

export const styles = StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: '#FFFDF7',
    },
    header: {
      backgroundColor: HEADER_BLUE,
      paddingHorizontal: 24,
      paddingBottom: 36,
      alignItems: 'center',
    },
    segmentedControl: {
      flexDirection: 'row',
      width: '100%',
      backgroundColor: HEADER_BLUE_DARK,
      borderRadius: 9999,
      alignSelf: 'center',
    },
    segment: {
      flex: 1,
      paddingVertical: 8,
      paddingHorizontal: 16,
      borderRadius: 9999,
      alignItems: 'center',
      justifyContent: 'center',
    },
    segmentActive: {
      backgroundColor: HEADER_BLUE,
      borderWidth: 1.5,
      borderColor: SEGMENT_ACTIVE_BORDER_COLOR,
    },
    segmentText: {
      fontSize: 16,
      fontWeight: '400',
      color: '#FFFFFF',
    },
    segmentTextActive: {
      color: '#FFFFFF',
      fontWeight: '700',
    },
    searchCardWrapper: {
      paddingHorizontal: 20,
      marginTop: -24,
      zIndex: 1,
    },
    searchCard: {
      backgroundColor: '#FFFFFF',
      borderRadius: 16,
      padding: 16,
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.08,
      shadowRadius: 12,
      elevation: 4,
    },
    searchInputRow: {
      gap: 12,
    },
    searchInput: {
      backgroundColor: '#F3F4F6',
      borderRadius: 12,
      paddingHorizontal: 16,
      paddingVertical: 14,
      fontSize: 16,
      color: '#111827',
    },
    searchInputLabel: {
      fontSize: 12,
      fontWeight: '500',
      color: '#6B7280',
      marginBottom: 6,
    },
    card: {
      flex: 1,
      backgroundColor: '#FFFFFF',
      borderTopLeftRadius: 24,
      borderTopRightRadius: 24,
      marginTop: 0,
      minHeight: 400,
      padding: 20,
    },
    linesCard: {
      backgroundColor: '#FFFFFF',
      borderRadius: 16,
      padding: 16,
      margin: 16,
      shadowColor: '#000',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.08,
      shadowRadius: 12,
      elevation: 4,
    },
    linesCardTitle: {
      fontSize: 18,
      fontWeight: '600',
      color: '#111827',
      marginBottom: 14,
    },
    tableHeader: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: 10,
      borderBottomWidth: 1,
      borderBottomColor: '#E5E7EB',
      marginBottom: 4,
    },
    tableRow: {
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: 12,
      borderBottomWidth: 1,
      borderBottomColor: '#F3F4F6',
    },
    tableCell: {
      flex: 1,
      fontSize: 15,
      color: '#374151',
    },
    tableCellIcon: {
      width: 40,
      alignItems: 'center',
      justifyContent: 'center',
    },
    tableHeaderText: {
      fontWeight: '600',
      color: '#6B7280',
      fontSize: 13,
    },
  });