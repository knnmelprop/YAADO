function [val,last,dir] = EVENTS(theta,z,gam)

% Event Handling for ode15s Solver
% PURPOSE
% - Stops the ODE solution when the cone wall is reached
% INPUTS
% - theta : Integration angle [rad]
% - z     : Angular and radial velocities
% - gam   : Ratio of specific heats
% 
% OUTPUTS
% - val      : Value of the ith event function
%              Event is triggered when value is 0
% - last     : Integration terminates at a zero of the event function
%                  if this value is 1, otherwise it's 0
% - dir      : If all zeros are to be located, 0
%                If zeros where event fnc decreasing, -1
%                If zeros where event fnc increasing, +1

val      = 1;             % No event triggered yet
last     = 1;             % Terminates after the first event is reached
dir      = 0;             % Get zeros from either direction (inc or dec)

% Trigger when angular velocity switches sign
% - Angular velocity needs to be zero at the cone surface (solid surface)

if (z(2) > 0)
    val = 0;              % If angular velocity z(2) crosses from
end                       %  being negative to positive, trigger event



