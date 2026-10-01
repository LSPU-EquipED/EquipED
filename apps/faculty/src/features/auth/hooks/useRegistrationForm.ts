import { useEffect, useRef, useState, type FormEvent } from 'react';
import { getErrorMessage } from '@equiped/api-client';
import {
  registrationApi,
  type RegistrationBody,
} from '../api/registration.api';

const initialForm: RegistrationBody = {
  name: '',
  email: '',
  password: '',
  faculty_id: '',
  department: '',
  program: '',
};
type PendingAction = 'start' | 'verify' | 'resend';

export function useRegistrationForm() {
  const [form, setForm] = useState(initialForm);
  const [token, setToken] = useState<string | null>(null);
  const [otp, setOtp] = useState('');
  const [done, setDone] = useState(false);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(
    null,
  );
  const [error, setError] = useState('');
  const [programError, setProgramError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const programRef = useRef<HTMLButtonElement>(null);
  const hadProgramError = useRef(false);
  const busy = pendingAction !== null;
  const pendingLabel =
    pendingAction === 'start'
      ? 'Sending code…'
      : pendingAction === 'verify'
        ? 'Verifying email…'
        : pendingAction === 'resend'
          ? 'Resending code…'
          : '';
  const update = (key: keyof RegistrationBody, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    // The dropdown changes its field wrapper when validation appears or clears.
    if (programError || hadProgramError.current) programRef.current?.focus();
    hadProgramError.current = Boolean(programError);
  }, [programError]);

  const start = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setError('');
    if (!form.program) {
      setProgramError('Select your program.');
      return;
    }
    setPendingAction('start');
    try {
      const response = await registrationApi.start({
        ...form,
        email: form.email.trim().toLowerCase(),
      });
      setToken(response.registration_token);
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to start registration.'));
    } finally {
      setPendingAction(null);
    }
  };
  const verify = async (event: FormEvent) => {
    event.preventDefault();
    if (!token || busy || otp.length !== 6) return;
    setError('');
    setPendingAction('verify');
    try {
      await registrationApi.verify(token, otp);
      setDone(true);
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to verify the code.'));
    } finally {
      setPendingAction(null);
    }
  };
  const resend = async () => {
    if (!token || busy) return;
    setError('');
    setPendingAction('resend');
    try {
      await registrationApi.resend(token);
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to resend the code.'));
    } finally {
      setPendingAction(null);
    }
  };

  const selectProgram = (value: string) => {
    update('program', value);
    setProgramError('');
  };

  return {
    form,
    token,
    otp,
    setOtp,
    done,
    pendingAction,
    pendingLabel,
    busy,
    error,
    programError,
    programRef,
    showPassword,
    setShowPassword,
    update,
    selectProgram,
    start,
    verify,
    resend,
  };
}
