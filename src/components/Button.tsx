import type { ButtonHTMLAttributes } from 'react'
import { Link, type LinkProps } from 'react-router'
import { buttonClass, pillClass, type ButtonSize, type ButtonVariant } from '../lib/ui'

interface StyleProps {
  variant?: ButtonVariant
  size?: ButtonSize
}

export function Button({
  variant,
  size,
  className,
  type = 'button',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & StyleProps) {
  return <button type={type} className={buttonClass(variant, size, className)} {...rest} />
}

export function ButtonLink({ variant, size, className, ...rest }: LinkProps & StyleProps) {
  return <Link className={buttonClass(variant, size, className)} {...rest} />
}

export function PillLink({ className = '', ...rest }: LinkProps) {
  return <Link className={`${pillClass} ${className}`} {...rest} />
}

export function PillButton({ className = '', type = 'button', ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type={type} className={`${pillClass} ${className}`} {...rest} />
}
