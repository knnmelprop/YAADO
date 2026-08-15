 function [z0] = TM_Equations(theta,z,k)


% State-space form of the Taylor-Maccoll equation used for integration
% INPUTS
% theta : Integration angle [rad]
% z     : Angular and radial velocities [m/s]
% k     : Ratio of specific heats
% 
% OUTPUTS
% z0  : Solution array

% Initialize solution vector
z0 = zeros(2,1);                                                            % z0(1) = dVr/dTheta
                                                                            % z0(2) = d2Vr/dTheta2
% Define term used often in equation below
A = (k-1)/2;

% Numerator and denominator for z0 calculation below
num = (-2*A*z(1)) - (A*z(2)*cot(theta)) + (2*A*z(1)^3) + ...                % Numerator of second state-space equation
      (A*z(1)^2*z(2)*cot(theta)) + (2*A*z(1)*z(2)^2) + ...
      (A*z(2)^3*cot(theta)) + (z(1)*z(2)^2);
den = A*(1-z(1)^2-z(2)^2) - z(2)^2;                                         % Denominator of second state-space equation

% State-space representation
z0(1) = z(2);
z0(2) = num/den;