import { Dimensions, StyleSheet } from 'react-native';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');

export const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    height: SCREEN_HEIGHT * 0.8,
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 12,
  },
  modalHandle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#D1D5DB',
    alignSelf: 'center',
    marginBottom: 16,
  },
  modalHeader: {
    paddingHorizontal: 24,
    marginBottom: 8,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
  },
  modalSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 4,
  },
  modalSummary: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 16,
    marginHorizontal: 24,
    backgroundColor: '#F0FDF4',
    borderRadius: 12,
    marginBottom: 16,
  },
  modalSummaryItem: {
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  modalSummaryValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#166534',
  },
  modalSummaryLabel: {
    fontSize: 12,
    color: '#15803D',
    marginTop: 2,
  },
  modalSummaryDivider: {
    width: 1,
    height: 28,
    backgroundColor: '#BBF7D0',
  },
  lineList: {
    paddingHorizontal: 24,
  },
  lineListContent: {
    paddingBottom: 24,
  },
  lineCard: {
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  lineCardSelected: {
    borderColor: '#09A6F3',
    backgroundColor: '#E0F2FE',
  },
  lineName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  lineNameSelected: {
    color: '#09A6F3',
  },
  lineDescription: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 4,
  },
  noLines: {
    textAlign: 'center',
    opacity: 0.5,
    fontStyle: 'italic',
    marginTop: 24,
  },
  newLineSection: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  newLineLabel: {
    fontSize: 13,
    fontWeight: '500',
    color: '#6B7280',
    marginBottom: 8,
  },
  newLineInput: {
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: '#111827',
  },
  modalActions: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderTopWidth: 1,
    borderTopColor: '#F3F4F6',
  },
  modalBtnCancel: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
  },
  modalBtnCancelText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  modalBtnConfirm: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#09A6F3',
    alignItems: 'center',
  },
  modalBtnConfirmDisabled: {
    opacity: 0.4,
  },
  modalBtnConfirmText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});
