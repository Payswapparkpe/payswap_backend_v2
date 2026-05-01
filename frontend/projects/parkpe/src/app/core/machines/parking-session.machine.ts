import { assign, setup } from 'xstate';
import type { Booking } from '../models/parking.model';

export type ParkingSessionStateValue =
  | 'idle'
  | 'initiated'
  | 'entered'
  | 'paymentPending'
  | 'awaitingUpiPayment'
  | 'completed'
  | 'disputed'
  | 'aborted';

export type ParkingSessionContext = {
  booking: Booking | null;
  elapsedSeconds: number;
  estimatedCostInr: number;
  errorMessage: string;
};

export type ParkingSessionEvent =
  | { type: 'RESTORE'; booking: Booking; elapsedSeconds?: number; estimatedCostInr?: number }
  | { type: 'ENTER'; booking: Booking; elapsedSeconds?: number; estimatedCostInr?: number }
  | { type: 'CANCEL' }
  | { type: 'TICK'; cost?: number }
  | { type: 'EXIT_TRIGGER' }
  | { type: 'PAYMENT_SUCCESS' }
  | { type: 'PAYMENT_FAILED'; reason: string }
  | { type: 'PAYMENT_UPI_REQUIRED' }
  | { type: 'UPI_PAID' }
  | { type: 'UPI_EXPIRED' }
  | { type: 'MANUAL_RESOLVE' }
  | { type: 'RESET' };

const initialContext: ParkingSessionContext = {
  booking: null,
  elapsedSeconds: 0,
  estimatedCostInr: 0,
  errorMessage: '',
};

/**
 * Mirrors backend ParkingSession lifecycle for consumer UI (active session widget + detail).
 */
export const parkingSessionMachine = setup({
  types: {
    context: {} as ParkingSessionContext,
    events: {} as ParkingSessionEvent,
  },
}).createMachine({
  id: 'parkingSession',
  context: initialContext,
  initial: 'idle',
  states: {
    idle: {
      on: {
        RESTORE: {
          target: 'entered',
          actions: assign({
            booking: ({ event }) => event.booking,
            elapsedSeconds: ({ event }) => event.elapsedSeconds ?? 0,
            estimatedCostInr: ({ event, context }) =>
              event.estimatedCostInr ?? context.estimatedCostInr ?? 0,
            errorMessage: () => '',
          }),
        },
        ENTER: {
          target: 'entered',
          actions: assign({
            booking: ({ event }) => event.booking,
            elapsedSeconds: ({ event }) => event.elapsedSeconds ?? 0,
            estimatedCostInr: ({ event, context }) =>
              event.estimatedCostInr ?? context.estimatedCostInr ?? 0,
            errorMessage: () => '',
          }),
        },
      },
    },
    initiated: {
      on: {
        ENTER: {
          target: 'entered',
          actions: assign({
            booking: ({ event }) => event.booking,
            elapsedSeconds: ({ event }) => event.elapsedSeconds ?? 0,
            estimatedCostInr: ({ event, context }) =>
              event.estimatedCostInr ?? context.estimatedCostInr ?? 0,
          }),
        },
        CANCEL: { target: 'aborted' },
      },
    },
    entered: {
      on: {
        TICK: {
          actions: assign({
            elapsedSeconds: ({ context }) => context.elapsedSeconds + 1,
            estimatedCostInr: ({ context, event }) =>
              event.cost !== undefined ? event.cost : context.estimatedCostInr,
          }),
        },
        EXIT_TRIGGER: { target: 'paymentPending' },
        RESET: { target: 'idle', actions: assign(() => ({ ...initialContext })) },
      },
    },
    paymentPending: {
      on: {
        PAYMENT_SUCCESS: { target: 'completed' },
        PAYMENT_FAILED: {
          target: 'disputed',
          actions: assign({ errorMessage: ({ event }) => event.reason }),
        },
        PAYMENT_UPI_REQUIRED: { target: 'awaitingUpiPayment' },
        RESET: { target: 'idle', actions: assign(() => ({ ...initialContext })) },
      },
    },
    awaitingUpiPayment: {
      on: {
        UPI_PAID: { target: 'completed' },
        UPI_EXPIRED: { target: 'disputed', actions: assign({ errorMessage: () => 'UPI window expired' }) },
        PAYMENT_SUCCESS: { target: 'completed' },
        RESET: { target: 'idle', actions: assign(() => ({ ...initialContext })) },
      },
    },
    completed: { type: 'final' },
    disputed: {
      on: {
        MANUAL_RESOLVE: { target: 'completed' },
        RESET: { target: 'idle', actions: assign(() => ({ ...initialContext })) },
      },
    },
    aborted: { type: 'final' },
  },
});
