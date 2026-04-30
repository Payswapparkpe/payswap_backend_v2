import { assign, setup } from 'xstate';

export type ExitFlowContext = {
  dueAmount: number;
  exitPaymentId: number | null;
  error: string;
};

export type ExitFlowEvent =
  | { type: 'PREVIEW_LOADED'; amount: number }
  | { type: 'PREVIEW_ERROR'; reason: string }
  | { type: 'NO_PAYMENT_DUE' }
  | { type: 'PAY_VOUCHER' }
  | { type: 'PAY_UPI' }
  | { type: 'SUCCESS' }
  | { type: 'FAILED'; reason: string }
  | { type: 'UPI_ORDER_CREATED'; exitPaymentId: number }
  | { type: 'POLL_SUCCESS' }
  | { type: 'POLL_TIMEOUT' }
  | { type: 'DONE' }
  | { type: 'RESET' };

const initialCtx: ExitFlowContext = {
  dueAmount: 0,
  exitPaymentId: null,
  error: '',
};

export const exitFlowMachine = setup({
  types: {
    context: {} as ExitFlowContext,
    events: {} as ExitFlowEvent,
  },
}).createMachine({
  id: 'exitFlow',
  initial: 'fetchingPreview',
  context: initialCtx,
  states: {
    fetchingPreview: {
      on: {
        PREVIEW_LOADED: {
          target: 'selectingMethod',
          actions: assign({ dueAmount: ({ event }) => event.amount, error: () => '' }),
        },
        PREVIEW_ERROR: {
          target: 'error',
          actions: assign({ error: ({ event }) => event.reason }),
        },
        NO_PAYMENT_DUE: 'completing',
      },
    },
    selectingMethod: {
      on: {
        PAY_VOUCHER: 'processingVoucher',
        PAY_UPI: 'processingUpi',
        RESET: { target: 'fetchingPreview', actions: assign(() => ({ ...initialCtx })) },
      },
    },
    processingVoucher: {
      on: {
        SUCCESS: 'completing',
        FAILED: {
          target: 'selectingMethod',
          actions: assign({ error: ({ event }) => event.reason }),
        },
      },
    },
    processingUpi: {
      on: {
        UPI_ORDER_CREATED: {
          target: 'pollingUpi',
          actions: assign({ exitPaymentId: ({ event }) => event.exitPaymentId }),
        },
        FAILED: {
          target: 'selectingMethod',
          actions: assign({ error: ({ event }) => event.reason }),
        },
      },
    },
    pollingUpi: {
      on: {
        POLL_SUCCESS: 'completing',
        POLL_TIMEOUT: {
          target: 'error',
          actions: assign({ error: () => 'Payment timed out. Contact attendant.' }),
        },
      },
    },
    completing: {
      on: {
        DONE: 'success',
      },
    },
    success: { type: 'final' },
    error: { type: 'final' },
  },
});
