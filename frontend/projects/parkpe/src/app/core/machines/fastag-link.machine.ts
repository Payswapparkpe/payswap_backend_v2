import { assign, setup } from 'xstate';

export type FastagLinkContext = {
  fastagId: string;
  issuer: string;
  vehicleId: string;
  error: string;
};

export type FastagLinkEvent =
  | { type: 'SUBMIT'; fastagId: string; issuer: string; vehicleId: string }
  | { type: 'VERIFY_SUCCESS' }
  | { type: 'VERIFY_FAILED'; reason: string }
  | { type: 'RESET' };

const initial: FastagLinkContext = {
  fastagId: '',
  issuer: '',
  vehicleId: '',
  error: '',
};

export const fastagLinkMachine = setup({
  types: {
    context: {} as FastagLinkContext,
    events: {} as FastagLinkEvent,
  },
}).createMachine({
  id: 'fastagLink',
  initial: 'enteringDetails',
  context: initial,
  states: {
    enteringDetails: {
      on: {
        SUBMIT: {
          target: 'verifying',
          actions: assign({
            fastagId: ({ event }) => event.fastagId,
            issuer: ({ event }) => event.issuer,
            vehicleId: ({ event }) => event.vehicleId,
            error: () => '',
          }),
        },
      },
    },
    verifying: {
      on: {
        VERIFY_SUCCESS: 'linked',
        VERIFY_FAILED: {
          target: 'enteringDetails',
          actions: assign({ error: ({ event }) => event.reason }),
        },
      },
    },
    linked: { type: 'final' },
  },
});
